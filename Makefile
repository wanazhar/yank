.PHONY: commit

commit:
	cd /home/ubuntu/work/yank && python3 _commit.py

status:
	cd /home/ubuntu/work/yank && git status --short

log:
	cd /home/ubuntu/work/yank && git log --oneline -5
