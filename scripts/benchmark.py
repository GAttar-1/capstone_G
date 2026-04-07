# ---------- benchmark.py ----------
# Run this script in your terminal: python benchmark.py
# It will test the RAG pipeline and generate an evaluation_report.csv

import os
import csv
import re
from datetime import datetime
from rag_pipeline import ask_ai

# --- CONFIGURATION: Define benchmark run version here ---
version = "3.5"  # Current Release
run_notes = "Full evaluation with dual-pass verification loop and 0.0 temperature." 
csv_filename = f"benchmark_run_v{version.replace('.', '_')}_{datetime.now().strftime('%Y%H%M')}.csv"

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
    
    if os.path.exists(excel_file):
        print(f"🔄 Appending newest run to the Master Excel workbook...")
        logo_path = os.path.abspath("reportingxpresslogo.jpg")
        
        # Build the script with string replacement to avoid f-string / brace madness
        ps_script_template = r"""
        $ErrorActionPreference = "Stop"
        $excel = New-Object -ComObject Excel.Application
        $excel.Visible = $false
        $excel.DisplayAlerts = $false
        try {
            $targetWb = $excel.Workbooks.Open('__EXCEL_FILE__')
            $sourceWb = $excel.Workbooks.Open('__CSV_FILE__')
            
            # 1. Determine Sequential Name
            $nextNum = 1
            foreach ($s in $targetWb.Sheets) {
                if ($s.Name -match "Google Antigravity [Uu]pdate (\d+)") {
                    $num = [int]$matches[1]
                    if ($num -ge $nextNum) { $nextNum = $num + 1 }
                }
            }
            $sheet_name = "Google Antigravity update $nextNum"
            Write-Host "Determined New Sheet Name: $sheet_name"

            # 2. Copy New Sheet to the FAR RIGHT
            $sourceSheet = $sourceWb.Sheets.Item(1)
            $lastSheet = $targetWb.Sheets.Item([int]$targetWb.Sheets.Count)
            $sourceSheet.Copy([System.Reflection.Missing]::Value, $lastSheet) | Out-Null
            $newSheet = $targetWb.Sheets.Item([int]$targetWb.Sheets.Count)
            $newSheet.Name = $sheet_name.ToString()
            
            # --- LIVE FORMULA UPGRADE: Individual Sheet ---
            $newSheet.Cells.Item(1, 7).Value2 = "__RUN_NOTES__" # Population of G1
            $lastR = [int]$newSheet.UsedRange.Rows.Count
            $newSheet.Cells.Item(1, 8).Formula = "=AVERAGE(C2:C$lastR)" # Population of H1
            $newSheet.Cells.Item(1, 8).NumberFormat = "0.0%"
            $newSheet.Cells.Item(1, 8).Font.Bold = $true
            
            $sourceWb.Close($false)

            # 3. Build/Refresh "Benchmark Summary" Dashboard (FAR LEFT)
            $summaryName = "Benchmark Summary"
            $summarySheet = $null
            foreach ($s in $targetWb.Sheets) {
                if ($s.Name -eq $summaryName) { $summarySheet = $s; break }
            }
            if (-not $summarySheet) {
                $summarySheet = $targetWb.Sheets.Add($targetWb.Sheets.Item(1))
                $summarySheet.Name = $summaryName.ToString()
            }
            $summarySheet.Move($targetWb.Sheets.Item(1)) | Out-Null
            $summarySheet.Cells.Clear() 

            # Dashboard Styling & Branding
            $summarySheet.Tab.ColorIndex = 37 # Light Blue tab
            
            # Insert Logo
            $logo = '__LOGO_PATH__'
            if (Test-Path $logo) {
                $shape = $summarySheet.Shapes.AddPicture($logo, $false, $true, 5, 5, 120, 60)
            }
            
            $summarySheet.Cells.Item(2, 3).Value2 = "📊 Reporting Xpress: RAG Performance Dashboard"
            $summarySheet.Cells.Item(2, 3).Font.Size = 18
            $summarySheet.Cells.Item(2, 3).Font.Bold = $true
            $summarySheet.Cells.Item(2, 3).Font.ColorIndex = 11 # Dark Blue

            $headers = @("Benchmark Version", "Avg Confidence Score", "Questions Tested", "Log Timestamp", "Notes")
            for ($i=0; $i -lt $headers.Count; $i++) {
                $cell = $summarySheet.Cells.Item(5, [int]($i+1))
                $cell.Value2 = $headers[$i].ToString()
                $cell.Font.Bold = $true
                $cell.Interior.ColorIndex = 11 # Dark Blue
                $cell.Font.ColorIndex = 2 # White
                $cell.HorizontalAlignment = -4108 # Center
            }

            # Rebuild Summary Table (5 Columns)
            $rowIdx = 6
            $processedSheets = New-Object System.Collections.Generic.HashSet[string]
            foreach ($sheet in $targetWb.Sheets) {
                $name = $sheet.Name.ToString()
                if ($name -ne $summaryName -and -not $processedSheets.Contains($name)) {
                    $processedSheets.Add($name) | Out-Null
                    $lastRow = [int]$sheet.UsedRange.Rows.Count
                    $count = 0
                    $timestamp = ""
                    $sheetNote = $sheet.Cells.Item(1, 7).Text # Pull from G1

                    for ($r=2; $r -le $lastRow; $r++) {
                        $tag = $sheet.Cells.Item([int]$r, 1).Value2
                        if ($tag -ne "SUMMARY" -and $tag -ne $null) {
                            $count++
                            if ($timestamp -eq "") { $timestamp = $sheet.Cells.Item([int]$r, 1).Value2.ToString() }
                        }
                    }
                    
                    $summarySheet.Cells.Item([int]$rowIdx, 1).Value2 = $name
                    $summarySheet.Cells.Item([int]$rowIdx, 2).Formula = "='" + $name + "'!`$H`$1"
                    $summarySheet.Cells.Item([int]$rowIdx, 2).NumberFormat = "0.0%"
                    $summarySheet.Cells.Item([int]$rowIdx, 3).Value2 = [int]$count
                    $summarySheet.Cells.Item([int]$rowIdx, 4).Value2 = $timestamp.ToString()
                    $summarySheet.Cells.Item([int]$rowIdx, 5).Value2 = $sheetNote.ToString() # New 5th column
                    
                    if ($rowIdx % 2 -eq 0) { $summarySheet.Range("A$rowIdx:E$rowIdx").Interior.ColorIndex = 34 }
                    $rowIdx++
                }
            }
            $summarySheet.Columns.AutoFit()

            # Dynamic Trend Chart
            if ($rowIdx -gt 6) {
                $chartRange = $summarySheet.Range("A5:B" + [int]($rowIdx - 1))
                $chartObj = $summarySheet.ChartObjects().Add(450, 80, 600, 350)
                $chart = $chartObj.Chart
                $chart.SetSourceData($chartRange)
                $chart.ChartType = 65 # xlLineMarkers
                $chart.HasTitle = $true
                $chart.ChartTitle.Text = "RAG Confidence Progression"
                $chart.Axes(1, 1).HasTitle = $true 
                $chart.Axes(1, 1).AxisTitle.Text = "Benchmark Version"
                $chart.Axes(2, 1).HasTitle = $true 
                $chart.Axes(2, 1).AxisTitle.Text = "Avg Confidence %"
                $chart.Axes(2, 1).MinimumScale = 0
                $chart.Axes(2, 1).MaximumScale = 100
            }

            $targetWb.Save()
            Write-Host "Success"
        } catch {
            Write-Host "Excel Error: $_"
        } finally {
            if ($targetWb) { $targetWb.Close($false) }
            $excel.Quit()
            [System.Runtime.Interopservices.Marshal]::ReleaseComObject($excel) | Out-Null
        }
        """
        ps_script = ps_script_template.replace("__EXCEL_FILE__", excel_file).replace("__CSV_FILE__", csv_abs_path).replace("__LOGO_PATH__", logo_path).replace("__RUN_NOTES__", run_notes)
        import subprocess
        result = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True)
        if "Success" in result.stdout:
            # Extract sheet name from PowerShell output if possible
            match = re.search(r"Determined New Sheet Name: (.*)", result.stdout)
            result_sheet = match.group(1).strip() if match else "New Update"
            print(f"✅ Successfully appended to {os.path.basename(excel_file)} as tab '{result_sheet}'!")
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