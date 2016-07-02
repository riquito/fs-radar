import pytest
import unittest


class FsRadatTest(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def initdir(self, tmpdir):
        tmpdir.chdir()  # change to pytest-provided temporary directory

        tmpdir.ensure('file_zero.txt')

        sub1 = tmpdir.join('sub1').mkdir()
        sub1.ensure('file_a.gz')
        sub1.ensure('file_b.tgz')

        sub2 = tmpdir.join('sub2').mkdir()
        sub2.ensure('file_c.gz')
        sub2.ensure('file_d.tgz')

        sub2_1 = sub2.join('sub2_1').mkdir()
        sub2_1.ensure('file_e.gz')
        sub2_1.ensure('file_f.tgz')
