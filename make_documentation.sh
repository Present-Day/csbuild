FILES=""
for i in csbuild/*.py; do
	if [ ${i:8:1} != "_" ]; then
		FILES="$FILES $i"
	fi
done

epydoc $FILES csbuild/__init__.py csbuild/_shared_globals.py --parse-only -v
