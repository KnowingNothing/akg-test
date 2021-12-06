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

"""transpose"""
import akg.topi
from akg.utils import custom_tiling as ct_util
from akg.utils import validation_check as vc_util
from akg.utils import kernel_exec as utils


transpose_set_dim_map = {
    str((((8, 24, 1, 1), (0, 2, 3, 1)), "float32")): ((8, 1), (1, 1), (1, 1), (1, 1)),
    str((((8, 24, 3, 3), (0, 2, 3, 1)), "float32")): ((8, 1), (3, 1), (3, 1), (1, 1)),
    str((((8, 36, 5, 5), (0, 2, 3, 1)), "float32")): ((8, 1), (5, 1), (5, 1), (1, 1)),
    str((((8, 36, 10, 10), (0, 2, 3, 1)), "float32")): ((8, 1), (10, 1), (10, 1), (1, 1)),
    str((((8, 36, 19, 19), (0, 2, 3, 1)), "float32")): ((8, 1), (19, 1), (19, 1), (1, 1)),
    str((((8, 24, 38, 38), (0, 2, 3, 1)), "float32")): ((2, 1), (38, 1), (38, 1), (1, 1)),
    str((((8, 16, 1, 1), (0, 2, 3, 1)), "float32")): ((8, 1), (1, 1), (1, 1), (16, 1)),
    str((((8, 16, 3, 3), (0, 2, 3, 1)), "float32")): ((8, 1), (3, 1), (3, 1), (1, 1)),
    str((((8, 24, 5, 5), (0, 2, 3, 1)), "float32")): ((8, 1), (5, 1), (5, 1), (1, 1)),
    str((((8, 24, 10, 10), (0, 2, 3, 1)), "float32")): ((8, 1), (10, 1), (10, 1), (1, 1)),
    str((((8, 24, 19, 19), (0, 2, 3, 1)), "float32")): ((8, 1), (19, 1), (19, 1), (1, 1)),
    str((((8, 16, 38, 38), (0, 2, 3, 1)), "float32")): ((2, 1), (38, 1), (38, 1), (1, 1)),
    str((((8, 1, 1, 16), (0, 3, 1, 2)), "float32")): ((8, 1), (16, 1), (1, 1), (1, 1)),
    str((((8, 3, 3, 16), (0, 3, 1, 2)), "float32")): ((8, 1), (16, 1), (1, 1), (1, 1)),
    str((((8, 38, 38, 16), (0, 3, 1, 2)), "float32")): ((2, 1), (1, 1), (38, 1), (38, 1)),
    str((((8, 128, 16, 64), (0, 2, 1, 3)), "float16")): ((4, 4), (8, 8), (16, 16), (64, 64)),
    str((((8, 38, 38, 24), (0, 3, 2, 1)), "float32")): ((8, 1), (24, 1), (1, 1), (1, 1)),  # success
    # str((((8, 38, 38, 24), (0, 3, 2, 1)), "float32")) : ((2, 1), (1, 1), (38, 1), (38, 1)), # nan, issue 699
    # str((((8, 38, 38, 24), (0, 3, 2, 1)), "float32")) : ((2, 1), (24, 1), (38, 1), (1, 1)), # assertion error
    str((((8, 38, 38, 24), (0, 3, 2, 1)), "float16")): ((8, 1), (24, 1), (1, 1), (1, 1)),
    str((((8, 24, 38, 38), (0, 3, 2, 1)), "float32")): ((8, 1), (38, 1), (1, 1), (1, 1)),
    str((((8, 24, 38, 38), (0, 3, 2, 1)), "float16")): ((8, 1), (38, 1), (1, 1), (1, 1)),
    str((((8, 16, 38, 38), (0, 3, 2, 1)), "float16")): ((8, 1), (1, 1), (1, 1), (16, 1)),
    str((((8, 16, 38, 38), (0, 3, 2, 1)), "float32")): ((8, 1), (1, 1), (1, 1), (16, 1)),

    # str((((8, 10, 10, 24), (0, 3, 2, 1)), "float16")) : ((1, 1), (1, 1), (1, 1), (16, 1)),
    # str((((8, 10, 10, 24), (0, 3, 2, 1)), "float32")) : ((1, 1), (1, 1), (1, 1), (16, 1)),
    # str((((8, 10, 10, 36), (0, 3, 2, 1)), "float16")) : ((1, 1), (1, 1), (1, 1), (16, 1)),
    # str((((8, 10, 10, 36), (0, 3, 2, 1)), "float32")) : ((1, 1), (1, 1), (1, 1), (16, 1)),
    # str((((8, 16, 3, 3), (0, 3, 2, 1)), "float16")) : ((1, 1), (1, 1), (1, 1), (16, 1)),
    # str((((8, 16, 3, 3), (0, 3, 2, 1)), "float32")) : ((1, 1), (1, 1), (1, 1), (16, 1)),

    # str((((8, 19, 19, 24), (0, 3, 2, 1)), "float16")) : ((1, 1), (1, 1), (1, 1), (16, 1)),
    # str((((8, 19, 19, 24), (0, 3, 2, 1)), "float32")) : ((1, 1), (1, 1), (1, 1), (16, 1)),
    # str((((8, 19, 19, 36), (0, 3, 2, 1)), "float16")) : ((1, 1), (1, 1), (1, 1), (16, 1)),
    # str((((8, 19, 19, 36), (0, 3, 2, 1)), "float32")) : ((1, 1), (1, 1), (1, 1), (16, 1)),
    # str((((8, 24, 10, 10), (0, 3, 2, 1)), "float16")) : ((1, 1), (1, 1), (1, 1), (16, 1)),
    # str((((8, 24, 10, 10), (0, 3, 2, 1)), "float32")) : ((1, 1), (1, 1), (1, 1), (16, 1)),
    # str((((8, 24, 3, 3), (0, 3, 2, 1)), "float16")) : ((1, 1), (1, 1), (1, 1), (16, 1)),
    # str((((8, 24, 3, 3), (0, 3, 2, 1)), "float32")) : ((1, 1), (1, 1), (1, 1), (16, 1)),

    # str((((8, 24, 5, 5), (0, 3, 2, 1)), "float16")) : ((1, 1), (1, 1), (1, 1), (16, 1)),
    # str((((8, 24, 5, 5), (0, 3, 2, 1)), "float32")) : ((1, 1), (1, 1), (1, 1), (16, 1)),
    # str((((8, 3, 3, 16), (0, 3, 2, 1)), "float16")) : ((1, 1), (1, 1), (1, 1), (16, 1)),
    # str((((8, 3, 3, 16), (0, 3, 2, 1)), "float32")) : ((1, 1), (1, 1), (1, 1), (16, 1)),
    # str((((8, 3, 3, 24), (0, 3, 2, 1)), "float16")) : ((1, 1), (1, 1), (1, 1), (16, 1)),
    # str((((8, 3, 3, 24), (0, 3, 2, 1)), "float32")) : ((1, 1), (1, 1), (1, 1), (16, 1)),
    # str((((8, 36, 10, 10), (0, 3, 2, 1)), "float16")) : ((1, 1), (1, 1), (1, 1), (16, 1)),
    # str((((8, 36, 10, 10), (0, 3, 2, 1)), "float32")) : ((1, 1), (1, 1), (1, 1), (16, 1)),
    # str((((8, 36, 5, 5), (0, 3, 2, 1)), "float16")) : ((1, 1), (1, 1), (1, 1), (16, 1)),
    # str((((8, 36, 5, 5), (0, 3, 2, 1)), "float32")) : ((1, 1), (1, 1), (1, 1), (16, 1)),
    # str((((8, 38, 38, 16), (0, 3, 2, 1)), "float16")) : ((1, 1), (1, 1), (1, 1), (16, 1)),
    # str((((8, 38, 38, 16), (0, 3, 2, 1)), "float32")) : ((1, 1), (1, 1), (1, 1), (16, 1)),
    # str((((8, 38, 38, 24), (0, 3, 2, 1)), "float16")) : ((1, 1), (1, 1), (1, 1), (16, 1)),
    # str((((8, 5, 5, 24), (0, 3, 2, 1)), "float16")) : ((1, 1), (1, 1), (1, 1), (16, 1)),
    # str((((8, 5, 5, 24), (0, 3, 2, 1)), "float32")) : ((1, 1), (1, 1), (1, 1), (16, 1)),
    # str((((8, 5, 5, 36), (0, 3, 2, 1)), "float16")) : ((1, 1), (1, 1), (1, 1), (16, 1)),
    # str((((8, 5, 5, 36), (0, 3, 2, 1)), "float32")) : ((1, 1), (1, 1), (1, 1), (16, 1)),
}


def transpose_set_dim_func(data, axes):
    key = []
    shape = [x.value for x in data.shape]
    key.append(tuple(shape))
    key.append(tuple(axes))

    hash_key = str((tuple(key), data.dtype))
    return ct_util.set_dims_by_key(hash_key, transpose_set_dim_map), hash_key


@ct_util.reg_set_dim_func(transpose_set_dim_func)
def transpose(data, axes):
    """ Transpose index from a tensor. """

    check_list = ["float16", "float32", "int32"]
    dtype = data.dtype
    if not (dtype.lower() in check_list):
        raise RuntimeError("transpose_cce only support %s while dtype is %s" % (",".join(check_list), dtype))
    shape = [x.value for x in data.shape]
    vc_util.check_shape(shape)

    assert len(shape) == len(axes), "length of shape and axes should be same"
    # if axes[-1] == len(shape) - 2:
    #     assert shape[-1] % 16 == 0, "transpose last axis only support 16xN number"
    attr_map = {"pragma_sink_last_axis": False}
    output = akg.topi.transpose(data, axes)
    return output, attr_map
