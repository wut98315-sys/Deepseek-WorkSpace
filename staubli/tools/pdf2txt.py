"""把 PDF 手册批量转成可检索的 UTF-8 文本。

用法:
    python pdf2txt.py <输入文件或目录> [更多输入...] [-o 输出目录]

例:
    python pdf2txt.py "D:\\手册" -o "D:\\7_deepseekWorkSpace\\staubli\\docs\\ref\\txt"

输出:
    每个 PDF 一个同名 .txt，外加 index.md（页数、字符数、抽取质量提示）。
"""
import sys
import os
import io
import argparse

try:
    import pypdf
except ImportError:
    sys.exit("缺少 pypdf：python -m pip install pypdf")


def collect(inputs):
    out = []
    for p in inputs:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in files:
                    if f.lower().endswith(".pdf"):
                        out.append(os.path.join(root, f))
        elif p.lower().endswith(".pdf"):
            out.append(p)
    return out


def unique_name(pdf, used):
    base = os.path.splitext(os.path.basename(pdf))[0]
    parent = os.path.basename(os.path.dirname(pdf))
    name = base
    n = 1
    while name in used:
        name = f"{base}_{parent}" if n == 1 else f"{base}_{parent}{n}"
        n += 1
    used.add(name)
    return name


def convert(pdf_path, out_dir, name):
    reader = pypdf.PdfReader(pdf_path)
    buf = io.StringIO()
    empty_pages = 0
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # 单页失败不影响整体
            text = ""
            buf.write(f"\n[第 {i} 页抽取失败: {exc}]\n")
        if not text.strip():
            empty_pages += 1
        buf.write(f"\n\n===== PAGE {i} =====\n")
        buf.write(text)

    body = buf.getvalue()
    target = os.path.join(out_dir, name + ".txt")
    with open(target, "w", encoding="utf-8") as fh:
        fh.write(body)

    return {
        "pdf": pdf_path,
        "txt": target,
        "pages": len(reader.pages),
        "empty_pages": empty_pages,
        "chars": len(body),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--out", default=".")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    pdfs = collect(args.inputs)
    if not pdfs:
        sys.exit("没有找到 PDF")

    used = set()
    rows = []
    for pdf in pdfs:
        try:
            info = convert(pdf, args.out, unique_name(pdf, used))
            rows.append(info)
            print(f"OK   {os.path.basename(pdf)}  {info['pages']} 页  {info['chars']} 字符")
        except Exception as exc:
            print(f"FAIL {os.path.basename(pdf)}: {exc}")

    index = os.path.join(args.out, "index.md")
    with open(index, "w", encoding="utf-8") as fh:
        fh.write("# 手册文本索引\n\n")
        fh.write("| 文件 | 页数 | 字符数 | 空白页 | 抽取质量 |\n|---|---|---|---|---|\n")
        for r in rows:
            ratio = r["empty_pages"] / r["pages"] if r["pages"] else 1
            quality = "OK" if ratio < 0.05 else ("部分缺字" if ratio < 0.5 else "几乎无文本(可能是扫描件)")
            fh.write(f"| {os.path.basename(r['txt'])} | {r['pages']} | {r['chars']} | {r['empty_pages']} | {quality} |\n")
    print(f"\n索引: {index}")


if __name__ == "__main__":
    main()
