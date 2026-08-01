# 中文转粤语声调

离线中文转粤语学习工具：输入普通中文，转换成日常粤语，并显示粤拼、声调线、中文近似译音、拆音学习和 macOS 离线朗读。

## 功能

- 普通中文 → 日常粤语表达
- 内置约 46 万条粤拼词库
- 词卡显示：粤语词、粤拼、中文译音、拆音、声调走势线
- 拆音学习：声母 + 韵母 + 声调形状
- 朗读：使用 macOS 自带粤语声音 `Sin-ji`，支持离线
- 输入记录：最近 / 一周 / 一月 / 一年
- 补充词库：用户可添加自己的粤语词和粤拼

## 运行

```bash
./scripts/run.sh
```

或直接：

```bash
python3 src/cantonese_tone_offline/app.py
```

自检：

```bash
./scripts/self_test.sh
```

## 打包 macOS App

```bash
./scripts/build_macos_app.sh
```

生成文件：

```text
dist/中文转粤语声调.app
dist/chinese-to-cantonese-tone-app-expanded.zip
```

安装到 `/Applications`：

```bash
./scripts/install_macos_app.sh
```

## 项目结构

```text
src/cantonese_tone_offline/app.py          主程序
src/cantonese_tone_offline/lexicon.json    粤拼词库
src/cantonese_tone_offline/s2t_opencc.json 简繁转换词库
app-template/                              macOS App 模板
scripts/run.sh                             本地运行
scripts/self_test.sh                       自检
scripts/build_macos_app.sh                 打包 app 和 zip
scripts/install_macos_app.sh               安装到 /Applications
```

## 数据和本地文件

程序运行时会把用户个人数据写到：

```text
~/Library/Application Support/中文转粤语声调/
```

这些个人数据不放进 Git：

- 输入记录.json
- 我的补充词库.txt
- 声调音频/

## 上传 Git 前建议

```bash
git status
git add README.md .gitignore requirements.txt src app-template scripts docs
git commit -m "Initial Cantonese tone offline app"
```
