# Omni3DEdit — Project Page

This is the GitHub project page for the paper:

> **Omni3DEdit: A Unified 3D Editing Benchmark with Region Annotations**  
> Hongxing Fan, Haotian Lu, Rui Chen, Weibin Yun, Zehuan Huang, Lu Sheng  
> ACM Multimedia 2026 — Dataset Track

## 🚀 Deploy to GitHub Pages

### Option A: 使用 GitHub Pages (推荐)

1. **在 GitHub 上创建仓库**
   - 前往 https://github.com/new
   - 仓库名称建议使用 `Omni3DEdit` 或 `omni3dedit.github.io`
   - 设为 **Public**

2. **将此目录推送到 GitHub**
   ```bash
   cd project_page
   git init
   git add .
   git commit -m "Initial project page"
   git branch -M main
   git remote add origin https://github.com/<YOUR_USERNAME>/Omni3DEdit.git
   git push -u origin main
   ```

3. **开启 GitHub Pages**
   - 打开仓库的 **Settings** → **Pages**
   - **Source** 选择 `Deploy from a branch`
   - **Branch** 选择 `main`，文件夹选 `/ (root)`
   - 点击 **Save**

4. **等待部署**
   - 前往仓库的 **Actions** 标签页查看构建进度
   - 部署完成后访问 `https://<YOUR_USERNAME>.github.io/Omni3DEdit/`

### Option B: 使用 GitHub Organization Page

如果你们有组织账号（如 `omni3dedit`），可以创建名为 `omni3dedit.github.io` 的仓库，这样访问地址会变成 `https://omni3dedit.github.io/`。

## 📁 文件结构

```
project_page/
├── index.html              # 主页面
├── README.md               # 本文件
└── static/
    ├── css/
    │   └── style.css       # 样式表
    ├── js/
    │   └── main.js         # 交互脚本
    └── images/
        ├── hero_banner.png     # 头图
        ├── subset_icons.png    # 子集图标
        └── pipeline_overview.png # 管线图
```

## ✏️ 自定义

### 替换占位链接
在 `index.html` 中搜索 `href="#"` 并替换为实际链接：

| 按钮 | 替换为 |
|------|--------|
| Paper | 你的论文 PDF 链接 |
| arXiv | arXiv 页面链接（如 `https://arxiv.org/abs/xxxx.xxxxx`） |
| Code | GitHub 代码仓库链接 |
| Dataset | 数据集下载链接（如 HuggingFace） |

### 添加论文实际图片
建议将论文中的 `teaser.pdf` 和 `method.pdf` 转换为 PNG 格式后替换 `static/images/` 中的占位图片：

```bash
# 使用 ImageMagick 转换
convert -density 300 ../figs/teaser.pdf static/images/hero_banner.png
convert -density 300 ../figs/method.pdf static/images/qualitative.png
```

### 更新实验结果
在 `index.html` 的结果表格（搜索 `results-table`）中，将 `—` 替换为实际的数值。

### 自定义域名（可选）
1. 在仓库根目录创建 `CNAME` 文件，写入你的域名
2. 在域名 DNS 中添加 CNAME 记录指向 `<YOUR_USERNAME>.github.io`

## 🎨 设计特点

- 🌙 现代暗色主题 + 玻璃拟态效果
- ✨ 滚动触发动画 + 数字动画计数器
- 📱 完全响应式设计（移动端适配）
- 📋 一键复制 BibTeX
- 🔍 SEO 优化（Open Graph + Twitter Card）

## 📄 License

This project page template is licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
