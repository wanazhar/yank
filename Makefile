.PHONY: push audit test clean verify build

push:
	cd /home/ubuntu/work/yank && git add -A && git commit -m "chore: bump to 0.2.0, audit fixes for PyPI release" && git push origin main

audit: clean verify test build
	@echo "=== AUDIT COMPLETE ==="

test:
	cd /home/ubuntu/work/yank && python3 -m pytest tests/test_formats.py tests/test_config.py tests/test_history.py tests/test_downloader.py tests/test_queue.py tests/test_updater.py -v --tb=short 2>&1 | tail -10

verify:
	cd /home/ubuntu/work/yank && python3 -c "from yank import __version__; print(f'version={__version__}')"
	cd /home/ubuntu/work/yank && python3 -c "from yank.app import YankApp; print('OK: YankApp imports')"

build:
	cd /home/ubuntu/work/yank && uv build --out-dir dist 2>&1 | tail -8
	ls dist/

clean:
	cd /home/ubuntu/work/yank && rm -rf dist/ build/ *.egg-info src/*.egg-info
	cd /home/ubuntu/work/yank && rm -f _commit.py _run_commit

