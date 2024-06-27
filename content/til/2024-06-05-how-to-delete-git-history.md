<!-- title: how to delete commit history of a git repository -->
There are a few ways to do it. The most obvious one is removing the `.git` directory and initiating `git` again. Another one is to create a orphan branch, deleting the other branches and renaming the orphan branch as `main`.

### Deleting `.git` directory:
```
rm -rf .git
git init
git remote add origin git@github.com:user/repo
git add *
git commit -am 'message'
git push -f origin main
```

### Orphan branch:
```
git checkout --orphan latest_branch
git add -A
git commit -am "commit message"
git branch -D main
git branch -m main
git push -f origin main
```
