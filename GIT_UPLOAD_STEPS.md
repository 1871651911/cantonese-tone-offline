# Git 上传步骤

## 1. 本地检查

```bash
cd cantonese-tone-offline-git
./scripts/self_test.sh
./scripts/build_macos_app.sh
git status
```

## 2. 提交

```bash
git add README.md .gitignore requirements.txt src app-template scripts docs GIT_UPLOAD_STEPS.md
git commit -m "Initial Cantonese tone offline app"
```

## 3. 关联远程仓库

GitHub 新建空仓库后，复制仓库地址，然后执行：

```bash
git remote add origin git@github.com:你的用户名/cantonese-tone-offline.git
git branch -M main
git push -u origin main
```

如果用 HTTPS：

```bash
git remote add origin https://github.com/你的用户名/cantonese-tone-offline.git
git branch -M main
git push -u origin main
```

## 4. 不上传的内容

`.gitignore` 已排除：

- `dist/`
- `*.app`
- `*.zip`
- `__pycache__/`
- 输入记录、补充词库、生成音频等本地个人数据

## 5. 发布包

打包文件在：

```text
dist/chinese-to-cantonese-tone-app-expanded.zip
```

这个 zip 建议放到 GitHub Release，不放进 Git 仓库源码。
