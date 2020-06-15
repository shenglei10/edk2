## @file
#  Check a patch for various format issues
#
#  Copyright (c) 2020, Intel Corporation. All rights reserved.<BR>
#
#  SPDX-License-Identifier: BSD-2-Clause-Patent
#

import os
import re
import csv
import subprocess
import argparse
import sys
import yaml
import shutil
import xml.dom.minidom
from typing import List, Dict, Tuple, Any

__copyright__ = "Copyright (c) 2020, Intel Corporation  All rights reserved."
ReModifyFile = re.compile(r'[B-Q,S-Z]+[\d]*\t(.*?)\n')
FindModifyFile = re.compile(r'\+\+\+ b\/(.*)')
LineScopePattern = (r'@@ -\d*\,*\d* \+\d*\,*\d* @@.*')
LineNumRange = re.compile(r'@@ -\d*\,*\d* \+(\d*)\,*(\d*) @@.*')

EnvList = os.environ
GlobalSymbol = {}
ignore_error_code = {
                             "10000",
                             "10001",
                             "10002",
                             "10003",
                             "10004",
                             "10005",
                             "10006",
                             "10007",
                             "10008",
                             "10009",
                             "10010",
                             "10011",
                             "10012",
                             "10013",
                             "10015",
                             "10016",
                             "10017",
                             "10022"
                            }
submodules = {
    "CryptoPkg/Library/OpensslLib/openssl",
    "ArmPkg/Library/ArmSoftFloatLib/berkeley-softfloat-3",
    "MdeModulePkg/Universal/RegularExpressionDxe/oniguruma",
    "MdeModulePkg/Library/BrotliCustomDecompressLib/brotli",
    "BaseTools/Source/C/BrotliCompress/brotli"
}

def AppendException(exception_list: List[str], exception_xml: str) -> None:
    error_code_list = exception_list[::2]
    keyword_list = exception_list[1::2]
    dom_tree = xml.dom.minidom.parse(exception_xml)
    root_node = dom_tree.documentElement
    for error_code, keyword in zip(error_code_list, keyword_list):
        customer_node = dom_tree.createElement("Exception")
        keyword_node = dom_tree.createElement("KeyWord")
        keyword_node_text_value = dom_tree.createTextNode(keyword)
        keyword_node.appendChild(keyword_node_text_value)
        customer_node.appendChild(keyword_node)
        error_code_node = dom_tree.createElement("ErrorID")
        error_code_text_value = dom_tree.createTextNode(error_code)
        error_code_node.appendChild(error_code_text_value)
        customer_node.appendChild(error_code_node)
        root_node.appendChild(customer_node)

    with open(exception_xml, 'w') as f:
        dom_tree.writexml(f, indent='', addindent='', newl='\n', encoding='UTF-8')


def GetPkgList() -> List[str]:
    WORKDIR = EnvList['WORKDIR']
    dirs = os.listdir(WORKDIR)
    pkg_list = []
    for directory in dirs:
        if directory.endswith('Pkg'):
            pkg_list.append(directory)
    return pkg_list


def GenerateEccReport(modify_dir_list: List[str], ecc_diff_range: Dict[str, List[Tuple[int, int]]]) -> None:
    ecc_need = False
    ecc_run = True
    pkg_list = GetPkgList()

    for line in modify_dir_list:
        print('Run ECC tool for the commit in %s' % line)
        GlobalSymbol['GenerateEccReport'] = True
        for pkg in pkg_list:
            if pkg in line:
                ecc_need = True
                ecc_cmd = ["py", "-3", "%WORKDIR%\\BaseTools\\Source\\Python\\Ecc\\EccMain.py",
                                 "-c", "%WORKDIR%\\BaseTools\\Source\\Python\\Ecc\\config.ini",
                                 "-e", "%WORKDIR%\\BaseTools\\Source\\Python\\Ecc\\exception.xml",
                                 "-t", "%WORKDIR%\\{}".format(line),
                                 "-r", "%WORKDIR%\\Ecc.csv"]
                _, _, result, return_code = ExecuteScript(ecc_cmd, EnvList, shell=True)
                if return_code != 0:
                    ecc_run = False
                    break

        if not ecc_run:
            print('Fail to run ECC tool')
            GlobalSymbol['SCRIPT_ERROR'] = True
            EndDelFile()

        if GlobalSymbol.get('GenerateEccReport'):
            ParseEccReport(ecc_diff_range)
        else:
            print("Patch check tool or ECC tool don't detect error")

    if ecc_need:
        revert_cmd = ["git", "checkout", "--", "%WORKDIR%\\BaseTools\\Source\\Python\\Ecc\\exception.xml"]
        _, _, result, return_code = ExecuteScript(revert_cmd, EnvList, shell=True)
    else:
        print("Doesn't need run ECC check")
        return


def ParseEccReport(ecc_diff_range: Dict[str, List[Tuple[int, int]]]) -> None:
    WORKDIR = EnvList['WORKDIR']
    ecc_log = os.path.join(WORKDIR, "Ecc.log")
    ecc_csv = "Ecc.csv"
    file = os.listdir(WORKDIR)
    row_lines = []
    if ecc_csv in file:
        with open(ecc_csv) as csv_file:
            reader = csv.reader(csv_file)
            for row in reader:
                for modify_file in ecc_diff_range:
                    if modify_file in row[3]:
                        for i in ecc_diff_range[modify_file]:
                            line_no = int(row[4])
                            if i[0] <= line_no <= i[1] and row[1] not in ignore_error_code:
                                row[0] = '\nEFI coding style error'
                                row[1] = 'Error code: ' + row[1]
                                row[3] = 'file: ' + row[3]
                                row[4] = 'Line number: ' + row[4]
                                row_line = '\n  *'.join(row)
                                row_lines.append(row_line)
                                break
                        break
    if row_lines:
        GlobalSymbol['ECC_PASS'] = False

    with open(ecc_log, 'a') as log:
        all_line = '\n'.join(row_lines)
        all_line = all_line + '\n'
        log.writelines(all_line)


def RemoveFile(file: str) -> None:
    if os.path.exists(file):
        os.remove(file)


def ExecuteScript(command: List[str], env_variables: Any, collect_env: bool = False,
                  enable_std_pipe: bool = False, shell: bool = True) -> Tuple[str, str, Dict[str, str], int]:
    env_marker = '-----env-----'
    env: Dict[str, str] = {}
    kwarg = {"env": env_variables,
             "universal_newlines": True,
             "shell": shell,
             "cwd": env_variables["WORKSPACE"]}

    if enable_std_pipe or collect_env:
        kwarg["stdout"] = subprocess.PIPE
        kwarg["stderr"] = subprocess.PIPE

    if collect_env:
        # get the binary that prints environment variables based on os
        if os.name == 'nt':
            get_var_command = "set"
        else:
            get_var_command = "env"
        # modify the command to print the environment variables
        if isinstance(command, list):
            command += ["&&", "echo", env_marker, "&&",
                        get_var_command, "&&", "echo", env_marker]
        else:
            command += " " + " ".join(["&&", "echo", env_marker,
                                       "&&", get_var_command,
                                       "&&", "echo", env_marker])

    # execute the command
    execute = subprocess.Popen(command, **kwarg)
    std_out, stderr = execute.communicate()
    code = execute.returncode

    # wait for process to be done
    execute.wait()

    # if collect enviroment variables
    if collect_env:
        # get the new environment variables
        std_out, env = GetEnvironmentVariables(std_out, env_marker)
    return (std_out, stderr, env, code)


def GetEnvironmentVariables(std_out_str: str, marker: str) -> Tuple[str, Dict[str, str]]:
    start_env_update = False
    environment_vars = {}
    out_put = ""
    for line in std_out_str.split("\n"):
        if start_env_update and len(line.split("=")) == 2:
            key, value = line.split("=")
            environment_vars[key] = value
        else:
            out_put += "\n" + line.replace(marker, "")

        if marker in line:
            if start_env_update:
                start_env_update = False
            else:
                start_env_update = True
    return (out_put, environment_vars)


def EndDelFile() -> None:
    WORKDIR = EnvList['WORKDIR']
    modify_file_list_log = os.path.join(WORKDIR, 'PatchModifyFiles.log')
    RemoveFile(modify_file_list_log)
    patch_log = os.path.join(WORKDIR, 'PatchFile.log')
    RemoveFile(patch_log)
    file_log = os.path.join(WORKDIR, "File.log")
    RemoveFile(file_log)
    if GlobalSymbol.get('GenerateEccReport'):
        file_list = os.listdir(WORKDIR)
        csv_list = [os.path.join(WORKDIR, file) for file in file_list if file.endswith('.csv')]
        for csv_file in csv_list:
            RemoveFile(csv_file)
    if GlobalSymbol.get('SCRIPT_ERROR'):
        print('ECC tool detect error')
        exit(1)


def GetDiffrange(commit: str) -> Dict[str, List[Tuple[int, int]]]:
    WORKDIR = EnvList['WORKDIR']
    range_directory: Dict[str, List[Tuple[int, int]]] = {}
    patch_log = os.path.join(WORKDIR, 'PatchFile.log')
    format_patch_cmd = ["git", "show", str(commit), "--unified=0", ">", patch_log]
    _, _, result, return_code = ExecuteScript(format_patch_cmd, EnvList, shell=True)
    if return_code != 0:
        print('Fail to run GIT')
        GlobalSymbol['SCRIPT_ERROR'] = True
        EndDelFile()
    with open(patch_log, encoding='utf8') as patch_file:
        file_lines = patch_file.readlines()
        IsDelete = True
        StartCheck = False
        for line in file_lines:
            modify_file = FindModifyFile.findall(line)
            if modify_file and not StartCheck and os.path.isfile(modify_file[0]):
                modify_file_comment_dic = GetCommentRange(modify_file[0])
                IsDelete = False
                StartCheck = True
                modify_file_dic = modify_file[0]
                modify_file_dic = modify_file_dic.replace("/", "\\")
                range_directory[modify_file_dic] = []
            elif line.startswith('--- '):
                StartCheck = False
            elif re.match(LineScopePattern, line, re.I) and not IsDelete and StartCheck:
                start_line = LineNumRange.search(line).group(1)
                line_range = LineNumRange.search(line).group(2)
                if not line_range:
                    line_range = '1'
                range_directory[modify_file_dic].append((int(start_line), int(start_line) + int(line_range) - 1))
                for i in modify_file_comment_dic:
                    if i[0] <= int(start_line) <= i[1]:
                        range_directory[modify_file_dic].append(i)
    return range_directory


def GetCommentRange(modify_file: str) -> List[Tuple[int, int]]:
    WORKDIR = EnvList['WORKDIR']
    modify_file_path = os.path.join(WORKDIR, modify_file)
    with open(modify_file_path) as f:
        line_no = 1
        comment_range: List[Tuple[int, int]] = []
        Start = False
        for line in f:
            if line.startswith('/**'):
                startno = line_no
                Start = True
            if line.startswith('**/') and Start:
                endno = line_no
                Start = False
                comment_range.append((int(startno), int(endno)))
            line_no += 1

    if comment_range and comment_range[0][0] == 1:
        del comment_range[0]
    return comment_range


def GetModifyDir(commit: str) -> List[str]:
    WORKDIR = EnvList['WORKDIR']
    modify_dir_list = []
    modify_file_list_log = os.path.join(WORKDIR, 'PatchModifyFiles.log')
    EnvList['ModifyFileListLog'] = modify_file_list_log
    patch_modify_cmd = ["git", "diff", "--name-status", str(commit), str(commit) + "~1", ">", modify_file_list_log]
    _, _, result, return_code = ExecuteScript(patch_modify_cmd, EnvList, shell=True)
    if return_code != 0:
        print('Fail to run GIT')
        GlobalSymbol['SCRIPT_ERROR'] = True
        EndDelFile()
    with open(modify_file_list_log) as modify_file:
        file_lines = modify_file.readlines()
    for Line in file_lines:
        file_path = ReModifyFile.findall(Line)
        if file_path:
            file_dir = os.path.dirname(file_path[0])
        else:
            continue
        pkg_list = GetPkgList()
        if file_dir in pkg_list or not file_dir:
            continue
        else:
            modify_dir_list.append('%s' % file_dir)

    modify_dir_list = list(set(modify_dir_list))
    return modify_dir_list


def ApplyConfig(modify_dir_list: List[str], ecc_diff_range: Dict[str, List[Tuple[int, int]]]) -> None:
    WORKDIR = EnvList['WORKDIR']
    modify_pkg_list = []
    for modify_dir in modify_dir_list:
        modify_pkg = modify_dir.split("/")[0]
        modify_pkg_list.append(modify_pkg)
    modify_pkg_list = list(set(modify_pkg_list))
    for modify_pkg in modify_pkg_list:
        pkg_config_file = os.path.join(WORKDIR, modify_pkg, modify_pkg + ".ci.yaml")
        if os.path.exists(pkg_config_file):
            with open(pkg_config_file, 'r') as f:
                pkg_config = yaml.safe_load(f)
            if "EccCheck" in pkg_config:
                ecc_config = pkg_config["EccCheck"]
                #
                # Add exceptions
                #
                exception_list = ecc_config["ExceptionList"]
                exception_xml = os.path.join(WORKDIR, "BaseTools", "Source", "Python", "Ecc", "exception.xml")
                if os.path.exists(exception_xml):
                    AppendException(exception_list, exception_xml)
                #
                # Exclude ignored files
                #
                ignore_file_list = ecc_config['IgnoreFiles']
                for ignore_file in ignore_file_list:
                    ignore_file = ignore_file.replace("/", "\\")
                    ignore_file = os.path.join(modify_pkg, ignore_file)
                    if ignore_file in ecc_diff_range:
                        del ecc_diff_range[ignore_file]
    return


def CheckOneCommit(commit: str) -> None:
    WORKDIR = EnvList['WORKDIR']
    if not WORKDIR.endswith('edk2') and not WORKDIR.endswith('Edk2') and not WORKDIR.endswith('\\s'):
        print(WORKDIR)
        print("Error: invalid workspace.\nBefore using EccCheck.py, please change workspace to edk2 root directory!")
        exit(1)
    modify_dir_list = GetModifyDir(commit)
    RemoveSubmodules(modify_dir_list)
    ecc_diff_range = GetDiffrange(commit)
    ApplyConfig(modify_dir_list, ecc_diff_range)
    GenerateEccReport(modify_dir_list, ecc_diff_range)
    EndDelFile()


def parse_options() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__copyright__)
    parser.add_argument('commits', nargs='*',
                        help='[commit(s) ID | number of commits, like "-3" means check first 3 commits]')
    args = parser.parse_args()
    return args


def read_commit_list_from_git(start_commit: str, count: int) -> List[str]:
    cmd = ['git', 'rev-list', '--abbrev-commit', '--no-walk']
    if count != 0:
        cmd.append('--max-count=' + str(count))
    cmd.append(start_commit)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    result = p.communicate()
    out = result[0].decode('utf-8', 'ignore') if result[0] and result[0].find(b"fatal") != 0 else None
    return out.split() if out else []


def ReleaseReport() -> int:
    WORKDIR = EnvList['WORKDIR']
    ecc_log = os.path.join(WORKDIR, "ECC.log")
    if GlobalSymbol['REMOVE_SUBMODULE']:
        cmd = ['git', 'submodule', 'update', '--init']
        _, _, result, return_code = ExecuteScript(cmd, EnvList, shell=True)
    if GlobalSymbol['ECC_PASS']:
        print('\n===================Ecc pass===================')
        RemoveFile(ecc_log)
        return 0
    else:
        print('\n===================Ecc error detected===================')
        with open(ecc_log) as output:
            print(output.read())
        RemoveFile(ecc_log)
        return -1

def RemoveSubmodules(modify_dir_list):
    WORKDIR = EnvList['WORKDIR']
    GlobalSymbol['REMOVE_SUBMODULE'] = False
    for modify_dir in modify_dir_list:
        for submodule in submodules:
            submodule_path = os.path.join(WORKDIR, submodule)
            if modify_dir in submodule_path:
                GlobalSymbol['REMOVE_SUBMODULE'] = True
                if os.path.exists(submodule_path):
                        shutil.rmtree(submodule_path)

def SetupEnvironment() -> None:
    WORKDIR = os.getcwd()
    EnvList['WORKDIR'] = WORKDIR
    EnvList['WORKSPACE'] = WORKDIR
    python_path = os.path.join(WORKDIR, "BaseTools", "Source", "Python")
    EnvList['PYTHONPATH'] = python_path


def main() -> int:
    commits = parse_options().commits

    if len(commits) == 0:
        commits = ['HEAD']

    if len(commits[0]) >= 2 and commits[0][0] == '-':
        count = int(commits[0][1:])
        commits = read_commit_list_from_git('HEAD', count)

    """
        This 'if' block is only used for creating pull request.
    """
    if ".." in commits[0]:
        commits = read_commit_list_from_git(commits[0], 0)

    GlobalSymbol['ECC_PASS'] = True

    SetupEnvironment()
    for commit in commits:
        CheckOneCommit(commit)

    retval = ReleaseReport()
    return retval


if __name__ == "__main__":
    sys.exit(main())
