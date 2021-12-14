# Copyright 2019 Huawei Technologies Co., Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import akg
from datetime import datetime
import logging
from enum import Enum
from tests.common.gen_random import random_gaussian
import numpy as np
from akg.utils import kernel_exec as utils
from akg.ops.nn import matmul
from tests.common.base import get_rtol_atol
from tests.common.tensorio import compare_tensor


logging.basicConfig(level=logging.DEBUG)


class MatmulType(Enum):
    gemm = 1
    gevm = 2
    gemv = 3


def get_name(caseIndex=1, name="leftMatrix", M=0, K=0, N=0, adj_x=False, adj_y=False):
    res = "{}_{}_{}_{}_{}_{}_{}.bin".format(
        caseIndex, name, M, K, N, adj_x, adj_y)
    return res


def get_shape(name="leftMatrix", M=0, K=0, N=0, batch_tuple=(1,), adj_x=False, adj_y=False):
    res_shape = ()
    if name == "leftMatrix":
        if adj_x:
            res_shape = batch_tuple + \
                (K // utils.BLOCK_REDUCE, M // utils.BLOCK_IN,
                 utils.BLOCK_REDUCE, utils.BLOCK_IN)
        else:
            res_shape = batch_tuple + \
                (M // utils.BLOCK_IN, K // utils.BLOCK_REDUCE,
                 utils.BLOCK_IN, utils.BLOCK_REDUCE)

    if name == "rightMatrix":
        if adj_y:
            res_shape = batch_tuple + \
                (N // utils.BLOCK_OUT, K // utils.BLOCK_REDUCE,
                 utils.BLOCK_REDUCE, utils.BLOCK_OUT)
        else:
            res_shape = batch_tuple + \
                (K // utils.BLOCK_REDUCE, N // utils.BLOCK_OUT,
                 utils.BLOCK_OUT, utils.BLOCK_REDUCE)

    if name == "result":
        res_shape = batch_tuple + \
            (N // utils.BLOCK_OUT, M // utils.BLOCK_IN,
             utils.BLOCK_IN, utils.BLOCK_OUT)
    return res_shape


def get_shapes(batch_tuple, M, K, N, trans_data=False, trans_weight=False):
    shape_x = batch_tuple + (M, K)
    if trans_data:
        shape_x = batch_tuple + (K, M)
    shape_y = batch_tuple + (K, N)
    if trans_weight:
        shape_y = batch_tuple + (N, K)
    return shape_x, shape_y


def getMatmulType(m, n):
    matmul_type = MatmulType.gemm
    if m // utils.BLOCK_IN == 0:
        matmul_type = MatmulType.gevm
    elif n == 1:
        matmul_type = MatmulType.gemv
    return matmul_type


def np_matmul(matrix_a, matrix_b, batch_tuple, M, K, N, trans_data=False, trans_weight=False, output_format=None):
    """
    implementation for the batch matmul
    :param matrix_a: (batch1, batch2, ..., M, K)
    :param matrix_b: (batch1, batch2, ..., K, N)
    :return:
    (batch1, batch2, ..., M, N)
    """
    batch_len = len(batch_tuple)
    if trans_data:
        matrix_a = matrix_a.transpose(
            tuple(range(batch_len)) + (batch_len + 1, batch_len))
    if trans_weight:
        matrix_b = matrix_b.transpose(
            tuple(range(batch_len)) + (batch_len + 1, batch_len))

    mul = 1
    for i in batch_tuple:
        mul = mul * i
    reshape_x = matrix_a.reshape(mul, M, K)
    reshape_y = matrix_b.reshape(mul, K, N)
    flatten_shape = (mul, M, N)
    out = np.zeros(flatten_shape, dtype=np.float16)
    for b in range(mul):
        out[b, :] = np.dot(reshape_x[b, :], reshape_y[b, :])
        #out[b,:] = np.matmul(reshape_x[b,:], reshape_y[b,:])
    matmul_type = getMatmulType(M, N)
    out_shape = ()
    if matmul_type == MatmulType.gemm:
        out_shape = batch_tuple + \
            (M // utils.BLOCK_IN, utils.BLOCK_IN,
             N // utils.BLOCK_OUT, utils.BLOCK_OUT)
    elif matmul_type == MatmulType.gevm:
        out_shape = batch_tuple + \
            (1, M % utils.BLOCK_IN, N // utils.BLOCK_OUT, utils.BLOCK_OUT)
    elif matmul_type == MatmulType.gemv:
        out_shape = batch_tuple + \
            (M // utils.BLOCK_IN, utils.BLOCK_IN, 1, N % utils.BLOCK_OUT)
    logging.debug(out_shape)
    # No Mo Mi Ni
    trans = tuple(range(batch_len)) + (batch_len + 2,
                                       batch_len, batch_len + 1, batch_len + 3)
    if output_format == "zZ":
        trans = tuple(range(batch_len)) + (batch_len,
                                           batch_len + 2, batch_len + 1, batch_len + 3)
    if matmul_type == MatmulType.gemv:
        # use the transpose of out
        trans = tuple(range(batch_len)) + (batch_len,
                                           batch_len + 2, batch_len + 3, batch_len + 1)
    res = out.reshape(out_shape).transpose(trans).copy()
    return res


def gen_data(batch_tuple, M, K, N, trans_data=False, trans_weight=False,
             dtype="float16", bias_dtype="float16", out_dtype="float16", bias=0, left_format="zZ", right_format="nZ", output_format="zN"):
    fractal_a, fractal_b, out, bias_data, _, _ = gen_data_all(
        batch_tuple, M, K, N, trans_data, trans_weight, dtype, bias_dtype, out_dtype, bias, left_format, right_format, output_format)
    return fractal_a, fractal_b, out, bias_data


def gen_data_all(batch_tuple, M, K, N, trans_data=False, trans_weight=False,
                 dtype="float16", bias_dtype="float16", out_dtype="float16", bias=0, left_format="zZ", right_format="nZ", output_format="zN"):
    shape_x, shape_y = get_shapes(
        batch_tuple, M, K, N, trans_data, trans_weight)
    matrix_a = random_gaussian(shape_x, miu=0.1, sigma=0.01).astype(dtype)
    matrix_b = random_gaussian(shape_y, miu=0.1, sigma=0.01).astype(dtype)

    # this change is for gen data speed
    matrix_a_for_np = matrix_a.astype(np.float32)
    matrix_b_for_np = matrix_b.astype(np.float32)

    matmul_type = getMatmulType(M, N)
    out = np_matmul(matrix_a_for_np, matrix_b_for_np, batch_tuple, M,
                    K, N, trans_data, trans_weight, output_format).astype(out_dtype)
    if dtype == "float16":
        out.astype(np.float16)

    bias_shape = (N,)
    bias_data = np.full(bias_shape, np.nan, bias_dtype)
    if bias != 0:
        bias_data = random_gaussian(
            bias_shape, miu=0.5, sigma=0.01).astype(bias_dtype)
        bias_reshape = (N // utils.BLOCK_OUT, 1, 1, utils.BLOCK_OUT)
        if output_format == "zZ":
            bias_reshape = (1, N // utils.BLOCK_OUT, 1, utils.BLOCK_OUT)
        bias_data_reshaped = bias_data.reshape(bias_reshape)
        if bias_dtype != out_dtype:
            out = out.astype(np.float32) + \
                bias_data_reshaped.astype(np.float32)
            out = out.astype(out_dtype)
        else:
            out = out + bias_data_reshaped

    shape_x = ()
    shape_y = ()
    if matmul_type == MatmulType.gemm:
        shape_x = (M // utils.BLOCK_IN, utils.BLOCK_IN, K //
                   utils.BLOCK_REDUCE, utils.BLOCK_REDUCE)
        if trans_data:
            shape_x = (K // utils.BLOCK_REDUCE, utils.BLOCK_REDUCE,
                       M // utils.BLOCK_IN, utils.BLOCK_IN)
        shape_y = (K // utils.BLOCK_REDUCE, utils.BLOCK_REDUCE,
                   N // utils.BLOCK_OUT, utils.BLOCK_OUT)
        if trans_weight:
            shape_y = (N // utils.BLOCK_OUT, utils.BLOCK_OUT, K //
                       utils.BLOCK_REDUCE, utils.BLOCK_REDUCE)
    elif matmul_type == MatmulType.gevm:
        shape_x = (1, M % utils.BLOCK_IN, K //
                   utils.BLOCK_REDUCE, utils.BLOCK_REDUCE)
        shape_y = (K // utils.BLOCK_REDUCE, utils.BLOCK_REDUCE,
                   N // utils.BLOCK_OUT, utils.BLOCK_OUT)
    elif matmul_type == MatmulType.gemv:
        # use traspose(b) transpose(a)
        shape_x = (M // utils.BLOCK_IN, utils.BLOCK_IN, K //
                   utils.BLOCK_REDUCE, utils.BLOCK_REDUCE)
        shape_y = (K // utils.BLOCK_REDUCE,
                   utils.BLOCK_REDUCE, 1, N % utils.BLOCK_OUT)

    batch_len = len(batch_tuple)
    # left_format zZ
    if left_format == "zZ":
        trans_x = tuple(range(batch_len)) + (batch_len + 0,
                                             batch_len + 2, batch_len + 1, batch_len + 3)
    elif left_format == "zN":
        trans_x = tuple(range(batch_len)) + (batch_len + 2,
                                             batch_len + 0, batch_len + 1, batch_len + 3)
    # right_format nZ
    if right_format == "nZ":
        trans_y = tuple(range(batch_len)) + (batch_len + 0,
                                             batch_len + 2, batch_len + 3, batch_len + 1)
    elif right_format == "zZ":
        trans_y = tuple(range(batch_len)) + (batch_len + 0,
                                             batch_len + 2, batch_len + 1, batch_len + 3)
    elif right_format == "zN":
        trans_y = tuple(range(batch_len)) + (batch_len + 2,
                                             batch_len + 0, batch_len + 1, batch_len + 3)
    fractal_a = matrix_a.reshape(
        batch_tuple + shape_x).transpose(trans_x).copy()
    fractal_b = matrix_b.reshape(
        batch_tuple + shape_y).transpose(trans_y).copy()
    if matmul_type == MatmulType.gemv:
        trans_y = tuple(range(batch_len)) + (batch_len + 2,
                                             batch_len + 0, batch_len + 3, batch_len + 1)
        trans_x = tuple(range(batch_len)) + (batch_len + 2,
                                             batch_len + 0, batch_len + 1, batch_len + 3)
        fractal_a = matrix_b.reshape(
            batch_tuple + shape_y).transpose(trans_y).copy()
        fractal_b = matrix_a.reshape(
            batch_tuple + shape_x).transpose(trans_x).copy()
    return fractal_a, fractal_b, out, bias_data, matrix_a, matrix_b


def matmul_data(batch_tuple, M, K, N, dtype, bias_dtype, out_dtype, bias, adj_x, adj_y, left_format=None, right_format=None, output_format=None, debug_logging=False):
    m_x = ()
    m_y = ()
    bench_mark = ()
    bias_data = ()
    logging.debug("gen data start!")
    a = datetime.now()
    m_x, m_y, bench_mark, bias_data = gen_data(
        batch_tuple, M, K, N, adj_x, adj_y, dtype, bias_dtype, out_dtype, bias, left_format, right_format, output_format)
    b = datetime.now()
    logging.debug((b - a).seconds)
    logging.debug("gen data end!")

    if debug_logging:
        logging.debug("m_x shape:{}".format(m_x.shape))
        logging.debug("m_y shape:{}".format(m_y.shape))
        logging.debug(type(m_x))
        logging.debug("bench_mark shape: {}".format(bench_mark.shape))

    return m_x, m_y, bench_mark, bias_data


def extract_dim(shape_x, shape_y, adj_x, adj_y):
    rank = len(shape_x)
    m = shape_x[-2] if adj_x == False else shape_x[-1]
    k = shape_x[-1] if adj_x == False else shape_x[-2]
    n = shape_y[-1] if adj_y == False else shape_y[-2]
    batch_tuple = shape_x[:-2] if rank > 2 else (1,)
    return batch_tuple, m, k, n


def reduce_data(reduce_type):
    res = utils.BLOCK_IN
    if reduce_type == "in":
        res = utils.BLOCK_IN
    elif reduce_type == "out":
        res = utils.BLOCK_OUT
    elif reduce_type == "reduce":
        res = utils.BLOCK_REDUCE
    return res


def get_fractal_shape(dim1, dim2, reduce1="in", reduce2="reduce", matrix_format="zZ"):
    result = ()
    dim1_reduce = reduce_data(reduce1)
    dim2_reduce = reduce_data(reduce2)
    if matrix_format == "zZ":
        result = (dim1 // dim1_reduce, dim2 //
                  dim2_reduce, dim1_reduce, dim2_reduce)
    elif matrix_format == "nZ":
        result = (dim1 // dim1_reduce, dim2 //
                  dim2_reduce, dim2_reduce, dim1_reduce)
    elif matrix_format == "nN":
        result = (dim2 // dim2_reduce, dim1 //
                  dim1_reduce, dim2_reduce, dim1_reduce)
    elif matrix_format == "zN":
        result = (dim2 // dim2_reduce, dim1 //
                  dim1_reduce, dim1_reduce, dim2_reduce)

    return result


def get_converted_shapes(m, n, k, batch_tuple, adj_x, adj_y, bias, left_format="zZ", right_format="nZ", out_format="zN"):
    matmul_type = getMatmulType(m, n)
    if matmul_type == MatmulType.gemm:
        # left_format zZ process
        if left_format == "zZ":
            shape_xx = batch_tuple + \
                get_fractal_shape(m, k, "in", "reduce", "zZ")
            if adj_x:
                shape_xx = batch_tuple + \
                    get_fractal_shape(m, k, "in", "reduce", "nN")
        # left_format zN process
        elif left_format == "zN":
            shape_xx = batch_tuple + \
                get_fractal_shape(m, k, "in", "reduce", "zN")
            if adj_x:
                shape_xx = batch_tuple + \
                    get_fractal_shape(m, k, "in", "reduce", "nZ")
        else:
            raise RuntimeError(
                "Error: unsupport left matrix format: %s" % left_format)

        # right_format nZ
        if right_format == "nZ":
            shape_yy = batch_tuple + \
                get_fractal_shape(k, n, "reduce", "out", "nZ")
            if adj_y:
                shape_yy = batch_tuple + \
                    get_fractal_shape(k, n, "reduce", "out", "zN")
        # right_format zZ
        elif right_format == "zZ":
            shape_yy = batch_tuple + \
                get_fractal_shape(k, n, "reduce", "out", "zZ")
            if adj_y:
                shape_yy = batch_tuple + \
                    get_fractal_shape(k, n, "reduce", "out", "nN")
        elif right_format == "zN":
            shape_yy = batch_tuple + \
                get_fractal_shape(k, n, "reduce", "out", "zN")
            if adj_y:
                shape_yy = batch_tuple + \
                    get_fractal_shape(k, n, "reduce", "out", "nZ")
        else:
            raise RuntimeError(
                "Error: unsupport right matrix format: %s" % right_format)

        # output_format zN
        # output_shape = batch_tuple + (n//utils.BLOCK_OUT, m//utils.BLOCK_IN, utils.BLOCK_IN, utils.BLOCK_OUT)
        if out_format == "zN":
            output_shape = batch_tuple + \
                get_fractal_shape(m, n, "in", "out", "zN")
        elif out_format == "zZ":
            output_shape = batch_tuple + \
                get_fractal_shape(m, n, "in", "out", "zZ")
        else:
            raise RuntimeError(
                "Error: unsupport output matrix format: %s" % out_format)

    elif matmul_type == MatmulType.gevm:
        shape_xx = batch_tuple + \
            (1, k // utils.BLOCK_REDUCE, m %
             utils.BLOCK_IN, utils.BLOCK_REDUCE)
        shape_yy = batch_tuple + \
            (k // utils.BLOCK_REDUCE, n // utils.BLOCK_OUT,
             utils.BLOCK_OUT, utils.BLOCK_REDUCE)
        output_shape = batch_tuple + \
            (n // utils.BLOCK_OUT, 1, m % utils.BLOCK_IN, utils.BLOCK_OUT)
    elif matmul_type == MatmulType.gemv:
        # transpose of b * transpose of a
        shape_xx = batch_tuple + \
            (1, k // utils.BLOCK_REDUCE, n %
             utils.BLOCK_IN, utils.BLOCK_REDUCE)
        shape_yy = batch_tuple + \
            (k // utils.BLOCK_REDUCE, m // utils.BLOCK_OUT,
             utils.BLOCK_OUT, utils.BLOCK_REDUCE)
        output_shape = batch_tuple + \
            (m // utils.BLOCK_OUT, 1, n % utils.BLOCK_IN, utils.BLOCK_OUT)

    if bias == 1:
        bias_shape_nc1hwc0 = (n,)
    else:
        bias_shape_nc1hwc0 = None
    return shape_xx, shape_yy, bias_shape_nc1hwc0, output_shape, k


def matmul_execute(
        shape_x, shape_y, bias,
        left_format, right_format, out_format,
        adj_x, adj_y, dtype, bias_dtype, out_dtype, kernel_name, attrs,
        dev_id=0, repeat=100):
    '''
    There are four types of fractal format in Davinci core: zZ, zN, nZ, nN
    general matmul format
    left_trans: False right_trans False: zZ * nZ = zN
    left_trans: True  right_trans False: nN * nZ = zN
    left_trans: False right_trans True : zZ * zN = zN
    left_trans: True  right_trans True : nN * zN = zN

    Now we need to support: zN * nZ = zN
    use left_format to specify, left matrix data format
    use right_format to specify, right matrix data format
    '''
    batch_tuple, m, k, n = extract_dim(shape_x, shape_y, adj_x, adj_y)
    m = (m + 15) // 16 * 16
    n = (n + 15) // 16 * 16
    k = (k + 15) // 16 * 16
    shape_xx, shape_yy, bias_shape, out_shape, k = get_converted_shapes(
        m, n, k, batch_tuple, adj_x, adj_y, bias, left_format, right_format, out_format)
    mod = matmul_compile(shape_x, shape_y, bias, left_format, right_format,
                         out_format, adj_x, adj_y, dtype, bias_dtype, out_dtype, kernel_name, attrs)
    # Generate data
    m_x, m_y, bench_mark, bias_data = matmul_data(
        batch_tuple, m, k, n, dtype, bias_dtype, out_dtype, bias, adj_x, adj_y, left_format, right_format, out_format)

    # mod launch
    output = np.full(out_shape, np.nan, out_dtype)
    if bias == 0:
        ctx = akg.tvm.context("cce", dev_id)
        import time
        t_mx = akg.tvm.nd.array(m_x, ctx)
        t_my = akg.tvm.nd.array(m_y, ctx)
        t_output = akg.tvm.nd.array(output, ctx)
        # warm up
        mod(t_mx, t_my, t_output)
        costs = []
        for i in range(repeat):
            ctx.sync()
            beg = time.time()
            mod(t_mx, t_my, t_output)
            ctx.sync()
            end = time.time()
            cost = (end - beg) * 1e3
            costs.append(cost)
        return np.mean(costs)
    elif bias == 1:
        ctx = akg.tvm.context("cce", dev_id)
        import time
        t_mx = akg.tvm.nd.array(m_x, ctx)
        t_my = akg.tvm.nd.array(m_y, ctx)
        t_bias = akg.tvm.nd.array(bias_data)
        t_output = akg.tvm.nd.array(output, ctx)
        # warm up
        mod(t_mx, t_my, t_bias, t_output)
        costs = []
        for i in range(repeat):
            ctx.sync()
            beg = time.time()
            mod(t_mx, t_my, t_bias, t_output)
            ctx.sync()
            end = time.time()
            cost = (end - beg) * 1e3
            costs.append(cost)
        return np.mean(costs)


def matmul_compile(shape_x, shape_y, bias, left_format, right_format, output_format, adj_x, adj_y, dtype, bias_dtype, out_dtype, kernel_name, attrs, tuning=False):
    batch_tuple, m, k, n = extract_dim(shape_x, shape_y, adj_x, adj_y)
    m = (m + 15) // 16 * 16
    n = (n + 15) // 16 * 16
    k = (k + 15) // 16 * 16
    shape_xx, shape_yy, bias_shape, out_shape, k = get_converted_shapes(m, n, k, batch_tuple, adj_x, adj_y, bias,
                                                                        left_format, right_format, output_format)
    input_shapes = [shape_xx, shape_yy, bias_shape]
    input_types = [dtype, dtype, bias_dtype]
    has_bias = False
    if bias == 1:
        has_bias = True
    op_attrs = [out_dtype, left_format, right_format,
                output_format, adj_x, adj_y, attrs]
    if has_bias == False:
        input_shapes = [shape_xx, shape_yy]
        input_types = [dtype, dtype]
        op_attrs = [None, out_dtype, left_format,
                    right_format, output_format, adj_x, adj_y, attrs]
    return utils.op_build_test(matmul.matmul, input_shapes, input_types, op_attrs, kernel_name, attrs, tuning=tuning)


yolo_shapes_b1 = [
    # batch, in_channel, height, width, out_channel, _, k_h, k_w, _, stride, padding, dilation, groups = shape
    # yolo
    (1, 3, 448, 448, 64, 3, 7, 7, 1, 2, 3, 1, 1),  # conv1  0
    (1, 64, 112, 112, 192, 64, 3, 3, 1, 1, 1, 1, 1),  # conv2   1
    (1, 192, 56, 56, 128, 192, 1, 1, 1, 1, 0, 1, 1),  # conv3   2
    (1, 128, 56, 56, 256, 128, 3, 3, 1, 1, 1, 1, 1),  # conv4   3
    (1, 256, 56, 56, 256, 256, 1, 1, 1, 1, 0, 1, 1),  # conv5   4
    (1, 256, 56, 56, 512, 256, 3, 3, 1, 1, 1, 1, 1),  # conv6   5
    (1, 512, 28, 28, 256, 512, 1, 1, 1, 1, 0, 1, 1),  # conv7   6
    (1, 256, 28, 28, 512, 256, 3, 3, 1, 1, 1, 1, 1),  # conv8   7
    (1, 512, 28, 28, 256, 512, 1, 1, 1, 1, 0, 1, 1),  # conv9
    (1, 256, 28, 28, 512, 256, 3, 3, 1, 1, 1, 1, 1),  # conv10
    (1, 512, 28, 28, 256, 512, 1, 1, 1, 1, 0, 1, 1),  # conv11
    (1, 256, 28, 28, 512, 256, 3, 3, 1, 1, 1, 1, 1),  # conv12
    (1, 512, 28, 28, 256, 512, 1, 1, 1, 1, 0, 1, 1),  # conv13
    (1, 256, 28, 28, 512, 256, 3, 3, 1, 1, 1, 1, 1),  # conv14
    (1, 512, 28, 28, 512, 512, 1, 1, 1, 1, 0, 1, 1),  # conv15      8
    (1, 512, 28, 28, 1024, 512, 3, 3, 1, 1, 1, 1, 1),  # conv16     9
    (1, 1024, 14, 14, 512, 1024, 1, 1, 1, 1, 0, 1, 1),  # conv17    10
    (1, 512, 14, 14, 1024, 512, 3, 3, 1, 1, 1, 1, 1),  # conv18     11
    (1, 1024, 14, 14, 512, 1024, 1, 1, 1, 1, 0, 1, 1),  # conv19
    (1, 512, 14, 14, 1024, 512, 3, 3, 1, 1, 1, 1, 1),  # conv20
    (1, 1024, 14, 14, 1024, 1024, 3, 3, 1, 1, 1, 1, 1),  # conv21   12
    (1, 1024, 14, 14, 1024, 1024, 3, 3, 1, 2, 1, 1, 1),  # conv22   13
    (1, 1024, 7, 7, 1024, 1024, 3, 3, 1, 1, 1, 1, 1),  # conv23     14
    (1, 1024, 7, 7, 1024, 1024, 3, 3, 1, 1, 1, 1, 1),  # conv24
]


fout = open("yolo_results.csv", "w")
print("M,N,K,cost(ms)", file=fout)
for (batch, in_channel, height, width, out_channel,
     _, k_h, k_w, _, stride, padding, dilation, groups) in yolo_shapes_b1:
    batch = 64
    R = (k_h - 1) * dilation + 1
    S = (k_w - 1) * dilation + 1
    P = (height + 2 * padding - R) // stride + 1
    Q = (width + 2 * padding - S) // stride + 1
    M = (batch * P * Q + 15) // 16 * 16
    N = (out_channel + 15) // 16 * 16
    K = (in_channel * k_h * k_w // groups + 15) // 16 * 16
    cost = matmul_execute(
        (M, K), (K, N), 0,
        "zZ", "nZ", "zN", False, False,
        "float16", "float16", "float16", "gemm", {},
        dev_id=6, repeat=100)
    print(f"{M},{N},{K},{cost}", file=fout)
    print(f"{M},{N},{K},{cost}")
