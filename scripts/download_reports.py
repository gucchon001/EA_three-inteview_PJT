"""Google Docs から全レポートをMarkdownとしてローカルに保存するスクリプト"""
import subprocess, json, sys, os

SCRIPT = os.path.join(os.path.dirname(__file__), "gdoc_to_md.py")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "samples", "notebooklm-reports")

REPORTS = [
    ("1W9qkhpYrBFd5QlatJ8OOQX3bIzpigH_cBTyscN85x0M", "儀賀_学習状況分析レポート.md"),
    ("15E3EqlbC43yk5Zyo7QlDPqtl2IB5SqYuz3CchCIcEqc", "学習状況分析レポート_テンプレ.md"),
    ("16xO70aFMr1ebp46oFxETIgoevm0mkrWlq6RDxBfZniU", "小林慧_学習分析レポート_2026年2月作成.md"),
    ("15IIST95J8mZ8NhYPWE5UbZIlVMxCHN58JwrzdjkC1LE", "武石_学習状況分析レポート_2026年3月.md"),
    ("1KoxzscZEHxVQRUlW9DoGlAaHjzPE9r05l8aGbLlbcms", "高藤_学習分析レポート_2026年2月度.md"),
    ("1EDG-CP2E8ChtEh_Jivs8beRC1IQYKDOUstECqEiHLLA", "川口_学習状況分析レポート.md"),
    ("1e7U0_t8FI33CN1KYXin3-tk9DomltwTqJsB_yDdSGUk", "高浜_学習状況分析レポート.md"),
    ("1gQZ6mJp8qHXXYrPYJARv1U6tX6YpUFfXfKGgrXWmXrM", "十倉_学習状況分析レポート_2026年3月.md"),
    ("1QykKwg4wuG9MrYOTpSI1YUKOYF9-2FrmVQSqNveYMn0", "和佐田_学習状況分析レポート_2026年3月.md"),
    ("15z_n5IunZJuHw4ZyoFoOeU4BqSTh_dXSANfL3nqU7BY", "IB数学_学習進捗戦略レポート.md"),
    ("1xFQoe74VPMCEBIJKJtS1LysykjITMjufEZ47uMBMJEo", "EDUBAL_学習状況分析および今後の学習計画レポート.md"),
    ("1vAsO6L9qxaAFy2WhGBtiY9Y-_JROAWRLaqudqjCdCJU", "ご家庭向け学習分析レポート.md"),
    ("1kRFDH2lP8lwTzXYBldKCzN452_fBuxGtqRs7P7UrC0M", "学習分析レポート_汎用テンプレ.md"),
    ("1UAYjTIOTzzekQMfs3Zg0kRrtSaPsmWvgZxBvczSmwyA", "小林慧_学習状況分析レポート.md"),
    ("1dDFUvrU6OMc2cbC5Iv7N-Hw7VA2C80eCo4WpLdEezHs", "ご家庭向け分析レポート_汎用テンプレ2.md"),
    ("1K_nVjCH-TCY2KhvfyUHonKfcnrA4LHuAJ5i7emcNf-s", "学習状況分析レポート_汎用テンプレ3.md"),
    ("10pULjkum_USdupO7j_ncbUq1CnLkPmoQwfayGoWmFac", "学習状況分析レポート_ご家庭向け.md"),
    ("1RnNA42YgtWQgU6A0gUx6e_QPO2Pud894O_ybnW0wWFE", "学習状況分析レポート_汎用.md"),
    ("19dwvBXqvAlkX-Yq7DMZ81Igo9C7tSWtYF9dwMl7YMsM", "高藤_学習状況分析レポート_2026年3月.md"),
    ("10wsx4aGMcrXlzDmLqL_qZbO5USF3w3c5mV_Ua0wO7Dc", "IB教育支援_新サービス開発提案レポート.md"),
    ("1vZQmuY4spOjVkNBO0gAvyygGt7cKsnifeCR1IhBgx7I", "標準化DX改善計画レポート.md"),
    ("1WzeHzt-16Xr3NpcCaskQHxso-aePbMA2V411A8EWzcU", "サービス改善分析レポート.md"),
    ("1_JoO6qkEfexeKph9hxKJftpTj39atBTgzZ--TC04iCo", "高藤_学習状況分析レポート_2026年2月20日.md"),
    ("13-Cx7N22ThiXIqE29zUijXS7KbZyMmqgd5JluOmAF_o", "高藤_学習分析レポート.md"),
    ("1bDpzRzQXHclwVrbuu1ynXVeW6t5wjw8vbub1GXlcfWQ", "Custom_Report.md"),
    ("1SPul3KjcxgGON33SMEbwam8Vz--6dmJI6rf_bUFJbcs", "高浜_学習状況分析レポート_2026年1月度.md"),
    ("1z4yINyNgxRplVnpa8MBxb2lLMqLasUSlq36iE1H9tds", "武石_学習状況分析レポート_2026年3月v2.md"),
    ("16J-1B6vg5F2U_vOeVHOaPq9oBzPTBENtV3Mm8wLuGnY", "川口_学習状況分析レポートv2.md"),
    ("1gcWD6BeDd9Jp9XeBkMI2-bSrbXJ-Ohp1xUj0fNlVjdg", "小林慧_学習分析レポート_2026年2月度.md"),
    ("1kDa2uJJeEvJEjsfa_8EfLtcwQ8d2MDKJrar4oZEWukE", "和佐田_学習分析レポート_2026年3月度.md"),
    ("1MlvzYLQoprZYEXDZp_COjYe6HhBBaUkrLLi9O7WOHUY", "十倉_学習状況分析レポート_2026年3月v2.md"),
    ("1p6lFtQYThScmjm4tv3yelEVp6thCleEDXAdi1TayKWE", "儀賀_学習状況分析レポート_2026年2月25日.md"),
    ("1c-5bWG4S1PR3Xo_k9JHTTO5dFYUI9UBQRn7AgR_uMt8", "月次メールおよびアップセル提案_運用詳細レポート.md"),
    ("1jo77ApMTPJIvhW9_LDqW4sb7TSnAXet92bSRNIG22v0", "教師ミーティング詳細レポート.md"),
    ("1Tkz-zuSrhEgB8wJCcgnqkyhyGGyG8dG2-ugxMYSFSiU", "個別面談報告書_生徒別指導現状と今後の学習計画.md"),
]

os.makedirs(OUT_DIR, exist_ok=True)
ok, ng = 0, 0

for doc_id, filename in REPORTS:
    out_path_check = os.path.join(OUT_DIR, filename)
    if os.path.exists(out_path_check) and os.path.getsize(out_path_check) > 0:
        print(f"SKIP {filename}")
        ok += 1
        continue
    out_path = os.path.join(OUT_DIR, filename)
    try:
        params = json.dumps({"documentId": doc_id})
        r1 = subprocess.run(
            f'gws docs documents get --params "{params.replace(chr(34), chr(92)+chr(34))}"',
            capture_output=True, shell=True
        )
        gws_text = r1.stdout.decode("utf-8", errors="replace")
        r2 = subprocess.run(
            f'python "{SCRIPT}"',
            input=gws_text.encode("utf-8"), capture_output=True, shell=True
        )
        r2_stdout = r2.stdout.decode("utf-8", errors="replace") if r2.stdout else ""
        r2_stderr = r2.stderr.decode("utf-8", errors="replace") if r2.stderr else ""
        if r2.returncode == 0 and r2_stdout.strip():
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(r2_stdout)
            print(f"OK {filename}")
            ok += 1
        else:
            print(f"NG {filename}: {r2_stderr.strip() or 'empty output'}")
            ng += 1
    except Exception as e:
        print(f"NG {filename}: {e}")
        ng += 1

print(f"\nDone: {ok} success / {ng} failed")
