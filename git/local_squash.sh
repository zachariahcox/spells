git checkout topic
git reset $(git merge-base target $(git branch --show-current))
git add -A
git commit -m "local squash"
