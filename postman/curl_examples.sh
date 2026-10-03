#!/bin/bash
# Sample cURL requests for testing Plum Medical Amount Detection API

BASE_URL="http://localhost:8000"

echo "=== 1. Health Check ==="
curl -s -X GET "${BASE_URL}/health" | jq .

echo -e "\n=== 2. Standard Text Input ==="
curl -s -X POST "${BASE_URL}/api/process" \
     -H "Content-Type: application/json" \
     -d '{"text": "Total: INR 1200 | Paid: 1000 | Due: 200 | Discount: 10%"}' | jq .

echo -e "\n=== 3. Noisy OCR Sample (Digit Confusion: l200 -> 1200) ==="
curl -s -X POST "${BASE_URL}/api/process" \
     -H "Content-Type: application/json" \
     -d '{"text": "T0tal: Rs l200 | Pald: 1000 | Due: 200"}' | jq .

echo -e "\n=== 4. Image Upload via Multipart Form ==="
curl -s -X POST "${BASE_URL}/api/process" \
     -F "file=@samples/sample_receipt_standard.png" | jq .

echo -e "\n=== 5. Noisy Document Guardrail Trigger ==="
curl -s -X POST "${BASE_URL}/api/process" \
     -H "Content-Type: application/json" \
     -d '{"text": "--- blurred smudge !!! @#$$%^ unreadable"}' | jq .

echo -e "\n=== 6. Full 4-Step Pipeline Trace ==="
curl -s -X POST "${BASE_URL}/api/pipeline" \
     -H "Content-Type: application/json" \
     -d '{"text": "T0tal: Rs l200 | Pald: 1000 | Due: 200"}' | jq .
