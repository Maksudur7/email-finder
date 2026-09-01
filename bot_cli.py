import argparse
import sys
import io
import pandas as pd
from email_engine import find_email_from_phone_and_name, bulk_find_emails

# Reconfigure stdout/stderr to handle unicode emojis on Windows console
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def main():
    parser = argparse.ArgumentParser(description="High-Precision Phone & Name to Email Finder Bot (CLI)")
    parser.add_argument("-p", "--phone", type=str, default="", help="Phone number to lookup (e.g. 01315906086)")
    parser.add_argument("-n", "--name", type=str, default="", help="Person name to lookup (e.g. Maksudur Rahaman Mishu)")
    parser.add_argument("-f", "--file", type=str, help="Path to input text/CSV file containing phone numbers")
    parser.add_argument("-o", "--output", type=str, default="email_results.csv", help="Output CSV file path")

    args = parser.parse_args()

    if args.phone or args.name:
        print(f"\n🔍 Searching Email for Name: '{args.name}' | Phone: '{args.phone}' ...")

        def progress_log(step, detail=""):
            print(f"  [{step}] {detail}")

        res = find_email_from_phone_and_name(
            phone=args.phone,
            name=args.name,
            progress_callback=progress_log
        )

        print("\n" + "="*60)
        print(f"Resolved Name  : {res['resolved_name']}")
        print(f"Primary Email  : {res['primary_email']}")
        print(f"SMTP Verified  : {len(res['smtp_verified'])} emails")

        if res['smtp_verified']:
            print("\n✅ Verified Real Emails:")
            for item in res['smtp_verified']:
                print(f"  - {item['email']} ({item['reason']})")

        print("\n📋 Top Email Candidates:")
        for em in res['all_emails_ranked'][:10]:
            print(f"  - {em}")
        print("="*60 + "\n")

    elif args.file:
        print(f"\n📁 Loading inputs from file: {args.file} ...")
        try:
            if args.file.endswith('.csv'):
                df = pd.read_csv(args.file)
                phone_col = [col for col in df.columns if 'phone' in col.lower() or 'number' in col.lower()]
                name_col = [col for col in df.columns if 'name' in col.lower()]

                p_col = phone_col[0] if phone_col else df.columns[0]
                n_col = name_col[0] if name_col else None

                phones = df[p_col].dropna().astype(str).tolist()
                names = df[n_col].dropna().astype(str).tolist() if n_col else None
            else:
                with open(args.file, 'r', encoding='utf-8') as f:
                    phones = [line.strip() for line in f if line.strip()]
                names = None

            print(f"🚀 Found {len(phones)} entries. Starting email lookup...\n")

            def print_progress(cur, total):
                sys.stdout.write(f"\rProgress: [{cur}/{total}] processed...")
                sys.stdout.flush()

            results = bulk_find_emails(phone_list=phones, name_list=names, callback=print_progress)
            print("\n\n✅ Search Completed!")

            out_data = []
            for r in results:
                out_data.append({
                    "Input Phone": r.get('input_phone', ''),
                    "Input Name": r.get('input_name', ''),
                    "Resolved Name": r.get('resolved_name', ''),
                    "Primary Email": r.get('primary_email', ''),
                    "Verified Emails": ", ".join(x['email'] for x in r.get('smtp_verified', [])),
                    "All Emails": ", ".join(r.get('all_emails_ranked', [])[:5])
                })

            out_df = pd.DataFrame(out_data)
            out_df.to_csv(args.output, index=False)
            print(f"💾 Results saved to: {args.output}\n")

        except Exception as e:
            print(f"❌ Error processing file: {e}")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
