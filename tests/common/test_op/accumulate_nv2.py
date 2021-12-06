# Copyright 2020 Huawei Technologies Co., Ltd
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

"""operator dsl function: accumulate_nv2"""
import akg
from akg.utils import validation_check as vc_util


def _accumulate_nv2_compute(x):
    """Compute accumulate_nv2"""

    dtype = x[0].dtype
    shape = x[0].shape
    length = len(x)

    result = x[0]
    # in order to improve the accuracy, convert float16 to float32
    if dtype == 'float16' and length > 1:
        result = akg.lang.cce.cast_to(result, 'float32')

    for i in range(1, length):
        rhs = x[i]
        if dtype == 'float16':
            rhs = akg.lang.cce.cast_to(x[i], 'float32')
        result = akg.lang.cce.vadd(result, rhs)

    if length == 1:
        # akg.lang.cce.vmuls supports float16, float32. int8, uint8, int32 will
        # be converted to float16. This will cause the data to be truncated.
        # so use akg.lang.cce.vmul.
        if dtype == "int32":
            value_one = akg.tvm.const(1, dtype=dtype)
            value_one_tensor = akg.lang.cce.broadcast(value_one, shape)
            result = akg.lang.cce.vmul(result, value_one_tensor)
        else:
            result = akg.lang.cce.vmuls(result, 1)

    if result.dtype != dtype:
        result = akg.lang.cce.cast_to(result, dtype)

    return result


@vc_util.check_input_type((list, tuple))
def accumulate_nv2(data):
    """
    Compute sum of all elements in tensor.

    Args:
        data (Union[tuple, list]): the list of input tensors of type float16, float32, int8, uint8, int32.

    Returns:
        tvm.tensor.Tensor, compute result, get all elements' sum.
    """
    for d in data:
        vc_util.ops_dtype_check(d.dtype, vc_util.DtypeForDavinci.ALL_TYPES)

    for i in range(1, len(data)):
        vc_util.elemwise_dtype_check(data[0].dtype, data[i].dtype)
        vc_util.elemwise_shape_check(data[0].shape, data[i].shape)

    res = _accumulate_nv2_compute(data)

    return res
