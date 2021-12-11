# The role of this code repository
We want to test the performance of AKG on Huawei Ascend 910 platforms.
But our environment is relatively closed.
We can't smoothly use git-lfs to push/pull files.
As a result, we decide to hard copy all the files of original AKG and test the performance.


# To build AKG
## Step 1.
Remember to modify the cmake/RT.cmake file to ensure your `ASCEND_RUNTIME_DIR` value points exactly to your ascend runtime. The default value may not work for your local environment.

## Step 2.
Change to root privileges on your ascend machine.
```sh
cd akg-test
bash build.sh -e ascend
```


# To run the test
Our test files are in /akg/tests/st/ops/ascend/mytest
```sh
cd /akg/tests
source test_env.sh
cd /akg/tests/st/ops/ascend/mytest
python3 test_ms_matmul.py
```
The results are in the csv file.
We can't use the time_evaluator currently for unknown reasons.
For a better evaluation, we should use it.
