import subprocess
import getpass
import tempfile
import os
import shutil
import unittest
from pathlib import Path
username = getpass.getuser()
cwd = os.getcwd()
script_path = Path(__file__).parent

yaml_data = f'''
username: {username}
ip: 127.0.0.1
port: 22
ssh_key_path: ~/.ssh/id_rsa
'''


class TestStringMethods(unittest.TestCase):
    def setUp(self):
        _, self.machine_data = tempfile.mkstemp()
        with open(self.machine_data,'w') as file:
            file.write(yaml_data)
        self.job_name = "test"

    def tearDown(self):
        os.remove(self.machine_data)
        if os.path.exists('job_results'):
            shutil.rmtree('job_results')

    def test_outputs(self):
        forward_data_path = script_path / "data" / "forward_data.txt"
        expected_data_path = script_path / "data" / "expected_result.txt"
        expected_data = open(expected_data_path).read()
        exec_command = f"sed s/robot/human/g {forward_data_path} | tee outfile.txt"
        test_command = f'execute_remote --machine {self.machine_data} --copy-forwards {forward_data_path} --copy-backwards outfile.txt --job-name={self.job_name} "{exec_command}"'
        res = subprocess.run(test_command, timeout=10, shell=True, stdout=subprocess.PIPE)
        self.assertEqual(res.returncode, 0, f"command failed with code {res.returncode}")
        actual_data = res.stdout.decode("utf-8")
        self.assertEqual(actual_data, expected_data)
        file_result = open(f'job_results/{self.job_name}/outfile.txt').read()
        self.assertEqual(file_result, expected_data)
