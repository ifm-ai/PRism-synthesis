
git config --global http.proxyAuthMethod basic
git config --global http.lowSpeedLimit 0
git config --global http.lowSpeedTime 999999
git config --global http.version HTTP/1.1
git config --global http.postBuffer 1048576000

rm -rf /workspace && mkdir -p /workspace && chmod 777 /workspace
cd /workspace
git init

git config advice.defaultBranchName false

git remote add origin 'https://github.com/googleapis/google-cloud-go.git'

git config remote.origin.promisor true
git config remote.origin.partialclonefilter "blob:none"

git fetch --depth 1 origin 'da245fac5ee335e86c63bfa5f165b0ab84960847'

git reset --hard FETCH_HEAD

git config user.email 'openenv@test.com'
git config user.name 'openenv-test'

rm -f .git/packed-refs
rm -rf .git/refs/tags .git/refs/remotes
git reflog expire --expire=now --all
git gc --prune=now --aggressive
git checkout -B 'main'
