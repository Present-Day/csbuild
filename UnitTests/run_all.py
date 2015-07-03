import subprocess
import sys
import os
import platform
import time
import re
from xml.etree import ElementTree

exitCode = 0

tests = [
	"Android/unit_test_android.py",
	"DependencyOrder/dependencyOrderTest.py",
	"Scope/scopeTest.py",
]

if platform.system() == "Darwin":
	tests.append(
		"OSX/HelloLibraries/make.py",
	)

csbuildPath = os.path.abspath("../")
os.putenv("PYTHONPATH", csbuildPath)

results = {}

ansi_escape = re.compile(r'\x1b[^m]*m')

for test in tests:
	print("================================================================================")
	print(">>> Running test {}".format(test))
	print("================================================================================")
	start = time.time()
	fd = subprocess.Popen( [ sys.executable, os.path.basename(test), "--rebuild" ] + sys.argv[1:], stdout = subprocess.PIPE, stderr=subprocess.PIPE, cwd = os.path.dirname(test) )

	(output, errors) = fd.communicate()

	if sys.version_info >= (3,0,0):
		output = output.decode("UTF-8")
		errors = errors.decode("UTF-8")

	results[test] = (re.sub(ansi_escape, "", output), re.sub(ansi_escape, "", errors), fd.returncode, time.time() - start)

	sys.stdout.write(output)
	sys.stderr.write(errors)

testSuiteName = "csbuild-python2" if "ython2" in sys.executable else "csbuild-python3"

root = ElementTree.Element("testsuite", name=testSuiteName, tests=str(len(tests)), errors=str(exitCode), failures=str(exitCode), skip="0")

for test, (output, errors, returnCode, runtime) in results.items():
	child = ElementTree.SubElement(root, "testcase", classname=os.path.splitext(os.path.basename(test))[0], name="UnitTest", time=str(runtime))
	if returnCode != 0:
		ElementTree.SubElement(child, "failure", type="Exit code", message="Process {} exited with non-zero exit code {}".format(test, returnCode))
	ElementTree.SubElement(child, "system-out").text=output
	ElementTree.SubElement(child, "system-err").text=errors

with open("result-{}.xml".format(testSuiteName), "wb") as f:
	ElementTree.ElementTree(root).write(f, encoding="UTF-8", xml_declaration=True)

sys.exit(exitCode)