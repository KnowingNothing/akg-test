#!/usr/bin/env python3
# coding: utf-8
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

"""operator dsl function: rec_positive"""

import akg.topi
import akg
from akg.utils import kernel_exec as utils
from akg.utils import validation_check as vc_util

@vc_util.check_input_type(akg.tvm.tensor.Tensor)
def rec_positive(x):
    """
    Calculate 1/x when data in x are all positive, used by dsl tanh and focalloss_grad.

    Args:
        x (tvm.tensor.Tensor): Tensor of type float16, float32. data in x must be positive.

    Returns:
        tvm.tensor.Tensor, the same type as inputs.
    """

    vc_util.ops_dtype_check(x.dtype, vc_util.DtypeForDavinci.ALL_FLOAT)
    need_conv = utils.product_is_mini() and x.dtype == "float32"
    x_fp16 = x
    if need_conv:
        x_fp16 = x.astype("float16")
    log = akg.topi.log(x_fp16)
    neg_log = akg.topi.negative(log)
    res = akg.lang.cce.vexp(neg_log)
    return res.astype(x.dtype) if need_conv else res
