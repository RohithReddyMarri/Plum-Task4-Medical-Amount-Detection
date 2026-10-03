let selectedFile = null;

const SAMPLES = {
    1: "Total: INR 1200 | Paid: 1000 | Due: 200 | Discount: 10%",
    2: "T0tal: Rs l200 | Pald: 1000 | Due: 200",
    3: "Hospital Invoice: Room charges INR 5000 | Medicine: INR 2500 | Total: INR 7500 | Amount Paid: 6000 | Balance Due: 1500",
    4: "--- corrupted scan --- !@#$%^&*() blurred line"
};

function switchTab(tab) {
    document.getElementById('tab-text').classList.toggle('active', tab === 'text');
    document.getElementById('tab-file').classList.toggle('active', tab === 'file');
    document.getElementById('text-input-panel').classList.toggle('active', tab === 'text');
    document.getElementById('file-input-panel').classList.toggle('active', tab === 'file');
}

function loadSample(num) {
    switchTab('text');
    document.getElementById('raw-text-input').value = SAMPLES[num] || "";
}

function handleFileSelected(event) {
    const file = event.target.files[0];
    if (file) {
        selectedFile = file;
        const reader = new FileReader();
        reader.onload = function(e) {
            document.getElementById('image-preview').src = e.target.result;
            document.getElementById('image-preview-container').style.display = 'flex';
            document.getElementById('dropzone').style.display = 'none';
        };
        reader.readAsDataURL(file);
    }
}

function clearImage() {
    selectedFile = null;
    document.getElementById('file-input').value = '';
    document.getElementById('image-preview').src = '';
    document.getElementById('image-preview-container').style.display = 'none';
    document.getElementById('dropzone').style.display = 'block';
}

function clearAll() {
    document.getElementById('raw-text-input').value = '';
    clearImage();
    ['step1', 'step2', 'step3', 'step4'].forEach(s => {
        document.getElementById(`output-${s}`).innerHTML = '<span class="placeholder-text">Awaiting pipeline run...</span>';
    });
    document.getElementById('guardrail-banner').style.display = 'none';
}

function formatJson(obj) {
    return JSON.stringify(obj, null, 2);
}

async function runPipeline() {
    const runBtn = document.getElementById('run-btn');
    const spinner = document.getElementById('btn-spinner');
    const banner = document.getElementById('guardrail-banner');
    
    runBtn.disabled = true;
    spinner.style.display = 'inline-block';
    banner.style.display = 'none';

    try {
        let response;
        if (selectedFile) {
            const formData = new FormData();
            formData.append('file', selectedFile);
            response = await fetch('/api/pipeline', {
                method: 'POST',
                body: formData
            });
        } else {
            const textVal = document.getElementById('raw-text-input').value.trim();
            if (!textVal) {
                alert('Please enter bill text or select an image.');
                return;
            }
            response = await fetch('/api/pipeline', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: textVal })
            });
        }

        const data = await response.json();

        // Step 1 Output
        if (data.step1_ocr) {
            document.getElementById('output-step1').innerHTML = `<pre>${formatJson(data.step1_ocr)}</pre>`;
        }

        // Step 2 Output
        if (data.step2_normalization) {
            document.getElementById('output-step2').innerHTML = `<pre>${formatJson(data.step2_normalization)}</pre>`;
        } else {
            document.getElementById('output-step2').innerHTML = '<span class="placeholder-text">Skipped</span>';
        }

        // Step 3 Output
        if (data.step3_classification) {
            document.getElementById('output-step3').innerHTML = `<pre>${formatJson(data.step3_classification)}</pre>`;
        } else {
            document.getElementById('output-step3').innerHTML = '<span class="placeholder-text">Skipped</span>';
        }

        // Step 4 Output
        if (data.step4_final) {
            document.getElementById('output-step4').innerHTML = `<pre>${formatJson(data.step4_final)}</pre>`;
        } else {
            document.getElementById('output-step4').innerHTML = '<span class="placeholder-text">Skipped</span>';
        }

        // Guardrail evaluation display
        banner.style.display = 'flex';
        if (data.status === 'guardrail_triggered' || !data.guardrails_passed) {
            banner.className = 'guardrail-box triggered';
            document.getElementById('guardrail-icon').innerText = '⚠️';
            document.getElementById('guardrail-title').innerText = 'Guardrail Triggered (Exit Condition)';
            document.getElementById('guardrail-desc').innerText = data.guardrail_notes.join(' | ') || 'Document too noisy or no amounts found.';
        } else {
            banner.className = 'guardrail-box';
            document.getElementById('guardrail-icon').innerText = '✅';
            document.getElementById('guardrail-title').innerText = 'Pipeline Complete & Guardrails Passed';
            document.getElementById('guardrail-desc').innerText = data.guardrail_notes.join(' • ');
        }

    } catch (err) {
        alert('Error executing pipeline: ' + err.message);
    } finally {
        runBtn.disabled = false;
        spinner.style.display = 'none';
    }
}
