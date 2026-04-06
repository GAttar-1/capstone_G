# ---------- benchmark.py ----------
# Run this script in your terminal: python benchmark.py
# It will test the RAG pipeline and generate an evaluation_report.csv

import csv
from datetime import datetime
from rag_pipeline import ask_ai

# Industry-standard test questions based on client minutes + CI Hub Analytics Library
TEST_QUESTIONS = [
    # --- Original 5 Test Questions ---
    "How do I identify top segment donors that are at risk of lapsing?",
    "What are the key metrics I should review before launching a campaign?",
    "What are the roles of the fundraiser in securing transformational gifts?",
    "How can we improve major donor retention?",
    "What is the best way to handle a donor who has stopped giving?",
    
    # --- Overall Fundraising Performance ---
    "How are we doing this year compared to last year?",
    "Are we on track to meet our annual goal?",
    "What drove the change in our revenue from last year?",
    "What does our giving history look like over many years?",
    "What will our revenue look like next year?",
    
    # --- Revenue Concentration & Structure ---
    "How dependent are we on our top donors?",
    "What does our giving pyramid look like?",
    "Who made the largest gifts last year?",
    "What's the split between individual and organizational giving?",
    
    # --- Donor Retention & Loyalty ---
    "What's our donor retention rate?",
    "How loyal are our top donors?",
    "Which donors give occasionally but not consistently?",
    "How long do our donors typically stay active?",
    "How do donors move between segments over time?",
    
    # --- Lapse Prevention & At-Risk Donors ---
    "Which donors are about to lapse?",
    "Which top donors have already lapsed?",
    "Which donors are giving less than they used to?",
    "Are my bottom donors at risk?",
    "How are gift counts trending — are donors giving less frequently?",
    
    # --- New Donor Acquisition & Onboarding ---
    "How many new donors did we acquire last year?",
    "Are new donors making a second gift?",
    "Are second-time donors making a third gift?",
    "What's our first-year donor retention rate?",
    "When during the year do we acquire the most new donors?",
    "How have our new donor acquisition trends changed over 10 years?",
    
    # --- Donor Upgrades & Growth Pipeline ---
    "Which donors are ready for a higher ask?",
    "Who are our best upgrade prospects for major gifts?",
    "How long does it take a donor to reach major gift level?",
    "Show me donors who started small and became major donors.",
    "What are the overall upgrade and downgrade patterns?",
    "Are our middle donors getting upgrade prospect lists?",
    
    # --- Recaptured / Reactivated Donors ---
    "Which lapsed donors came back this year?",
    "Which segment are our recaptures coming from?",
    "What does our 10-year recapture history look like?",
    
    # --- Donor Scoring & Risk Assessment ---
    "How do I score my top donors for risk and opportunity?",
    "How do I score middle donors?",
    "Can I see scores for all donors at once?",
    
    # --- Segmentation & Data Foundation ---
    "What are our segment definitions and thresholds?",
    "What does our raw segmentation data look like?",
    "What are the probabilities of donors transitioning between segments?",
    "How do I understand the lifetime value of different donor cohorts?",
    
    # --- Seasonal & Timing Patterns ---
    "When is our peak giving month?",
    "Do Giving Tuesday donors give at other times?",
    "Which months produce the most new donors?",
    "Which donors gave us a big lift in a specific month?",
    
    # --- Predictive & Statistical Models ---
    "Can CI Hub predict future giving behavior?",
    "How reliable is the projection model?",
    
    # --- Major Donor Journey & Development ---
    "How do donors become major donors? Are they born or made?",
    "How long does it take to develop a major donor?",
    "What does a successful major donor growth path look like?",
    "What does it take to reach the million-dollar lifetime giving mark?",
    "What are the upgrade probabilities at each stage?",
    "Who are our most loyal long-term major donors?",
    "Can we predict which current donors will become major donors?",
    
    # --- Major Gift Officer / Portfolio Management ---
    "Show me a dashboard for my top donors.",
    "How are my top donors tracking this year vs last year?",
    "Who are the linchpin donors driving our current results?",
    "What do the $1 million lifetime donors look like?"
]

def run_evaluation():
    print(f"📊 Starting RAG Evaluation for {len(TEST_QUESTIONS)} questions...\n")
    
    results = []
    
    for i, question in enumerate(TEST_QUESTIONS, 1):
        print(f"[{i}/{len(TEST_QUESTIONS)}] Testing: {question}")
        
        # Call the pipeline (we turn off the logic explanation to save processing time)
        response = ask_ai(question, require_logic=False)
        
        # Extract the data
        answer = response.get("answer", "Error generating answer.")
        confidence = response.get("avg_confidence", 0)
        
        print(f"   ↳ Confidence: {confidence:.2f}%")
        
        # Format the sources into a clean, readable string
        sources = [src["id"] for src in response.get("sources", [])]
        sources_str = " | ".join(sources) if sources else "None Found"
        
        results.append({
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Question": question,
            "Confidence Score": f"{confidence:.1f}%",
            "Sources Used": sources_str,
            "AI Answer": answer
        })
        
    # Calculate Average Confidence
    avg_confidence = 0
    if results:
        total_conf = sum(float(r["Confidence Score"].replace("%", "")) for r in results)
        avg_confidence = total_conf / len(results)
    # Calculate Average Confidence for Summary
    avg_confidence = 0
    if results:
        # We use a clean results list (excluding the summary row if it was added)
        numeric_results = [r for r in results if r["Timestamp"] != "SUMMARY"]
        total_conf = sum(float(r["Confidence Score"].replace("%", "")) for r in numeric_results)
        avg_confidence = total_conf / len(numeric_results)
    
    # Append the Summary/Average row to the results (for the CSV itself)
    results.append({
        "Timestamp": "SUMMARY",
        "Question": "AVERAGE CONFIDENCE SCORE",
        "Confidence Score": f"{avg_confidence:.2f}%",
        "Sources Used": "",
        "AI Answer": ""
    })

    with open(csv_filename, mode="w", newline="", encoding="utf-8") as file:
        fieldnames = ["Timestamp", "Question", "Confidence Score", "Sources Used", "AI Answer"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    print(f"\n✅ Evaluation complete! Results saved to {csv_filename}")

    # Auto-append to Combined_Benchmark_Results.xlsx using PowerShell COM automation
    excel_file = os.path.abspath("Combined_Benchmark_Results.xlsx")
    csv_abs_path = os.path.abspath(csv_filename)
    # The user specifed "Google Antigravity #" naming convention
    sheet_name = f"Google Antigravity {version}"
    
    if os.path.exists(excel_file):
        print(f"🔄 Appending {sheet_name} to the Master Excel workbook...")
        ps_script = f"""
        $ErrorActionPreference = "Stop"
        $excel = New-Object -ComObject Excel.Application
        $excel.Visible = $false
        $excel.DisplayAlerts = $false
        try {{
            $targetWb = $excel.Workbooks.Open('{excel_file}')
            $sourceWb = $excel.Workbooks.Open('{csv_abs_path}')
            $sourceSheet = $sourceWb.Sheets.Item(1)
            $lastSheet = $targetWb.Sheets.Item($targetWb.Sheets.Count)
            $sourceSheet.Copy([System.Reflection.Missing]::Value, $lastSheet)
            $newSheet = $targetWb.Sheets.Item($targetWb.Sheets.Count)
            $newSheet.Name = '{sheet_name}'
            
            # Place the Average Confidence in Cell H1
            $newSheet.Cells.Item(1, 8).Value = 'Average Confidence: {avg_confidence:.2f}%'
            $newSheet.Cells.Item(1, 8).Font.Bold = $true
            
            $sourceWb.Close($false)
            $targetWb.Save()
            Write-Host "Success"
        }} catch {{
            Write-Host "Excel Append Error: $_"
        }} finally {{
            if ($targetWb) {{ $targetWb.Close($false) }}
            $excel.Quit()
            [System.Runtime.Interopservices.Marshal]::ReleaseComObject($excel) | Out-Null
        }}
        """
        import subprocess
        result = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True)
        if "Success" in result.stdout:
            print(f"✅ Successfully appended to {os.path.basename(excel_file)} as tab '{sheet_name}'!")
            # Cleanup: Delete the CSV after successful merge as requested
            try:
                os.remove(csv_filename)
                print(f"🗑️ Deleted temporary file: {csv_filename}")
            except Exception as e:
                print(f"⚠️ Could not delete CSV: {e}")
        else:
            print(f"⚠️ Failed to append to Excel. Output: {result.stdout} {result.stderr}")
    else:
        print(f"⚠️ Master workbook not found at {excel_file}. Skipping Excel merge.")

if __name__ == "__main__":
    run_evaluation()