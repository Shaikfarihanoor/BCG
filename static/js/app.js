/**
 * CertiCraft Studio - Frontend Client Application
 * Handles job submission, real-time polling, PDF preview modals, and UI interactions.
 */

// Application State
const state = {
  activeJobId: null,
  pollInterval: null,
  certificates: [],
  currentFilter: 'all',
  theme: localStorage.getItem('certicraft_theme') || 'dark',
};

// Initial Sample Roster
const SAMPLE_RECIPIENTS = [
  { name: 'Asha Rao', email: 'asha.rao@example.com' },
  { name: 'Ravi Kumar', email: 'ravi.kumar@example.com' },
  { name: 'Dr. Priya Swaminathan', email: 'priya.swami@institution.edu' },
  { name: '', email: 'missing.name@example.com' }, // Demo failure row
];

// DOM Elements
const jobForm = document.getElementById('jobForm');
const eventNameInput = document.getElementById('eventName');
const issueDateInput = document.getElementById('issueDate');
const recipientListContainer = document.getElementById('recipientListContainer');
const recipientCountBadge = document.getElementById('recipientCountBadge');
const addRowBtn = document.getElementById('addRowBtn');
const loadSampleBtn = document.getElementById('loadSampleBtn');
const clearRowsBtn = document.getElementById('clearRowsBtn');
const openImportBtn = document.getElementById('openImportBtn');
const submitBtn = document.getElementById('submitBtn');
const submitBtnText = document.getElementById('submitBtnText');

// Dashboard Elements
const activeJobMeta = document.getElementById('activeJobMeta');
const jobStatusBadgeSlot = document.getElementById('jobStatusBadgeSlot');
const statTotal = document.getElementById('statTotal');
const statCompleted = document.getElementById('statCompleted');
const statFailed = document.getElementById('statFailed');
const statPending = document.getElementById('statPending');
const progressBar = document.getElementById('progressBar');
const progressPercent = document.getElementById('progressPercent');
const countAll = document.getElementById('countAll');
const countCompleted = document.getElementById('countCompleted');
const countFailed = document.getElementById('countFailed');
const certificatesTableBody = document.getElementById('certificatesTableBody');
const downloadZipBtn = document.getElementById('downloadZipBtn');
const retryFailedBtn = document.getElementById('retryFailedBtn');

// Modals
const pdfModal = document.getElementById('pdfModal');
const pdfPreviewFrame = document.getElementById('pdfPreviewFrame');
const modalPdfTitle = document.getElementById('modalPdfTitle');
const importModal = document.getElementById('importModal');
const importTextarea = document.getElementById('importTextarea');
const toastContainer = document.getElementById('toastContainer');
const themeToggleBtn = document.getElementById('themeToggleBtn');
const apiStatusText = document.getElementById('apiStatusText');
const apiStatusBadge = document.getElementById('apiStatusBadge');

// Initialization
document.addEventListener('DOMContentLoaded', () => {
  // Apply saved theme
  document.documentElement.setAttribute('data-theme', state.theme);

  // Set default issue date to today
  const today = new Date().toISOString().split('T')[0];
  issueDateInput.value = today;

  // Load initial demo recipients
  loadRoster(SAMPLE_RECIPIENTS);

  // Check backend health
  checkApiHealth();

  // Attach Event Listeners
  addRowBtn.addEventListener('click', () => addRecipientRow());
  loadSampleBtn.addEventListener('click', () => loadRoster(SAMPLE_RECIPIENTS));
  clearRowsBtn.addEventListener('click', () => clearRoster());
  openImportBtn.addEventListener('click', () => openImportModal());
  jobForm.addEventListener('submit', handleFormSubmit);
  themeToggleBtn.addEventListener('click', toggleTheme);

  // Close modals on ESC
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closePdfModal();
      closeImportModal();
    }
  });
});

// Theme Management
function toggleTheme() {
  state.theme = state.theme === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', state.theme);
  localStorage.setItem('certicraft_theme', state.theme);
}

// Health Check
async function checkApiHealth() {
  try {
    const res = await fetch('/health');
    if (res.ok) {
      apiStatusText.textContent = 'Engine Online';
      apiStatusBadge.style.color = 'var(--accent-emerald)';
    } else {
      throw new Error();
    }
  } catch {
    apiStatusText.textContent = 'Backend Offline';
    apiStatusBadge.style.color = 'var(--accent-rose)';
  }
}

// Event Preset Quick Select
window.setEventPreset = function (name) {
  eventNameInput.value = name;
  eventNameInput.focus();
};

// Recipient Row Management
function addRecipientRow(name = '', email = '') {
  const row = document.createElement('div');
  row.className = 'recipient-row';
  row.innerHTML = `
    <input type="text" class="recipient-input rec-name" placeholder="Full Name" value="${escapeHtml(name)}">
    <input type="email" class="recipient-input rec-email" placeholder="Email Address" value="${escapeHtml(email)}">
    <button type="button" class="row-delete-btn" title="Remove Recipient" onclick="removeRow(this)">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
    </button>
  `;
  recipientListContainer.appendChild(row);
  updateRecipientCount();
}

window.removeRow = function (btn) {
  const row = btn.closest('.recipient-row');
  if (row) {
    row.remove();
    updateRecipientCount();
  }
};

function clearRoster() {
  recipientListContainer.innerHTML = '';
  updateRecipientCount();
}

function loadRoster(roster) {
  clearRoster();
  roster.forEach(r => addRecipientRow(r.name, r.email));
}

function updateRecipientCount() {
  const count = recipientListContainer.querySelectorAll('.recipient-row').length;
  recipientCountBadge.textContent = `${count} Recipient${count === 1 ? '' : 's'}`;
}

// Import Modal Handling
window.openImportModal = function () {
  importModal.classList.add('active');
  importTextarea.focus();
};

window.closeImportModal = function () {
  importModal.classList.remove('active');
};

window.processImportText = function () {
  const text = importTextarea.value.trim();
  if (!text) {
    showToast('Please paste some text first', 'info');
    return;
  }

  const lines = text.split('\n');
  let added = 0;

  lines.forEach(line => {
    line = line.trim();
    if (!line) return;
    let parts = line.split(',');
    if (parts.length < 2) parts = line.split('\t');

    const name = (parts[0] || '').trim();
    const email = (parts[1] || '').trim();
    if (name || email) {
      addRecipientRow(name, email);
      added++;
    }
  });

  closeImportModal();
  importTextarea.value = '';
  showToast(`Parsed and added ${added} recipients`, 'success');
};

// Form Submission & Job Creation
async function handleFormSubmit(e) {
  e.preventDefault();

  const eventName = eventNameInput.value.trim();
  const issueDate = issueDateInput.value.trim();

  if (!eventName) {
    showToast('Event name is required', 'error');
    return;
  }

  const rows = recipientListContainer.querySelectorAll('.recipient-row');
  if (rows.length === 0) {
    showToast('Please add at least one recipient', 'error');
    return;
  }

  const recipients = [];
  rows.forEach(row => {
    recipients.push({
      name: row.querySelector('.rec-name').value.trim(),
      email: row.querySelector('.rec-email').value.trim(),
    });
  });

  // UI Loading State
  submitBtn.disabled = true;
  submitBtnText.textContent = 'Submitting & Scheduling...';

  try {
    const payload = {
      event_name: eventName,
      issue_date: issueDate,
      recipients: recipients,
    };

    const res = await fetch('/api/v1/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Server returned ${res.status}`);
    }

    const data = await res.json();
    state.activeJobId = data.job_id;
    showToast(`Job ${data.job_id.slice(0, 8)} accepted! Processing in background.`, 'success');

    // Start live polling
    startPolling(data.job_id);

  } catch (err) {
    showToast(`Submission failed: ${err.message}`, 'error');
  } finally {
    submitBtn.disabled = false;
    submitBtnText.textContent = 'Generate Certificates in Bulk';
  }
}

// Live Status Polling
function startPolling(jobId) {
  if (state.pollInterval) clearInterval(state.pollInterval);

  // Immediate poll
  fetchJobStatus(jobId);

  // Poll every 800ms
  state.pollInterval = setInterval(() => {
    fetchJobStatus(jobId);
  }, 800);
}

async function fetchJobStatus(jobId) {
  try {
    const res = await fetch(`/api/v1/jobs/${jobId}?limit=200`);
    if (!res.ok) return;

    const job = await res.json();
    state.certificates = job.certificates || [];

    updateDashboard(job);

    // Stop polling if job has completed or failed
    if (['COMPLETED', 'COMPLETED_WITH_ERRORS', 'FAILED'].includes(job.status)) {
      clearInterval(state.pollInterval);
      state.pollInterval = null;

      if (job.status === 'COMPLETED') {
        showToast('All certificates generated successfully!', 'success');
      } else if (job.status === 'COMPLETED_WITH_ERRORS') {
        showToast('Job completed with isolated errors', 'info');
      } else if (job.status === 'FAILED') {
        showToast('Job processing failed', 'error');
      }
    }
  } catch (err) {
    console.error('Error polling job status:', err);
  }
}

// Update Dashboard View
function updateDashboard(job) {
  activeJobMeta.textContent = `Job ID: ${job.job_id.slice(0, 8)}... • Event: ${job.event_name}`;

  // Status Badge
  let badgeClass = 'badge-pending';
  if (job.status === 'COMPLETED') badgeClass = 'badge-completed';
  if (job.status === 'FAILED') badgeClass = 'badge-failed';
  if (job.status === 'COMPLETED_WITH_ERRORS') badgeClass = 'badge-failed';

  jobStatusBadgeSlot.innerHTML = `
    <span class="badge ${badgeClass}">
      <span class="status-dot"></span>
      ${job.status.replace(/_/g, ' ')}
    </span>
  `;

  // Stats Counters
  statTotal.textContent = job.total;
  statCompleted.textContent = job.completed;
  statFailed.textContent = job.failed;
  statPending.textContent = job.pending;

  // Progress Bar
  const totalProcessed = job.completed + job.failed;
  const percent = job.total > 0 ? Math.round((totalProcessed / job.total) * 100) : 0;
  progressBar.style.width = `${percent}%`;
  progressPercent.textContent = `${percent}%`;

  // Download ZIP Button
  if (job.completed > 0) {
    downloadZipBtn.style.display = 'inline-flex';
    downloadZipBtn.href = `/api/v1/jobs/${job.job_id}/download`;
  } else {
    downloadZipBtn.style.display = 'none';
  }

  // Retry Failed Button
  if (job.failed > 0 && job.status !== 'PROCESSING') {
    retryFailedBtn.style.display = 'inline-flex';
  } else {
    retryFailedBtn.style.display = 'none';
  }

  // Tab counts
  countAll.textContent = job.total;
  countCompleted.textContent = job.completed;
  countFailed.textContent = job.failed;

  // Render Table Rows
  renderCertificatesTable();
}

// Filter Tabs
window.setFilter = function (filter) {
  state.currentFilter = filter;
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-filter') === filter);
  });
  renderCertificatesTable();
};

// Render Table
function renderCertificatesTable() {
  const filtered = state.certificates.filter(c => {
    if (state.currentFilter === 'all') return true;
    return c.status === state.currentFilter;
  });

  if (filtered.length === 0) {
    certificatesTableBody.innerHTML = `
      <tr>
        <td colspan="4" style="text-align:center; padding:2rem; color:var(--text-dim)">
          No certificates matching current filter.
        </td>
      </tr>
    `;
    return;
  }

  certificatesTableBody.innerHTML = filtered.map(cert => {
    let statusBadge = '';
    if (cert.status === 'COMPLETED') {
      statusBadge = `<span class="badge badge-completed">COMPLETED</span>`;
    } else if (cert.status === 'FAILED') {
      const errorTooltip = cert.error ? escapeHtml(cert.error) : 'Generation failed';
      statusBadge = `<span class="badge badge-failed" title="${errorTooltip}">FAILED: ${errorTooltip.slice(0, 32)}...</span>`;
    } else {
      statusBadge = `<span class="badge badge-pending">PENDING</span>`;
    }

    let actions = '';
    if (cert.status === 'COMPLETED' && cert.download_url) {
      actions = `
        <div style="display:flex; gap:0.4rem;">
          <button class="table-action-btn" onclick="previewPdf('${cert.download_url}', '${escapeHtml(cert.recipient_name || 'Certificate')}')">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
            Preview
          </button>
          <a href="${cert.download_url}" class="table-action-btn" download title="Download PDF">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
            PDF
          </a>
        </div>
      `;
    } else if (cert.status === 'FAILED') {
      actions = `<span style="font-size:0.75rem; color:var(--accent-rose);">${escapeHtml(cert.error || 'Failed')}</span>`;
    } else {
      actions = `<span style="font-size:0.75rem; color:var(--text-dim);">Generating...</span>`;
    }

    return `
      <tr>
        <td style="font-weight:600;">${escapeHtml(cert.recipient_name || '—')}</td>
        <td style="color:var(--text-muted);">${escapeHtml(cert.recipient_email || '—')}</td>
        <td>${statusBadge}</td>
        <td>${actions}</td>
      </tr>
    `;
  }).join('');
}

// PDF Modal
window.previewPdf = function (url, title) {
  modalPdfTitle.textContent = `Certificate Preview - ${title}`;
  pdfPreviewFrame.src = url;
  pdfModal.classList.add('active');
};

window.closePdfModal = function () {
  pdfModal.classList.remove('active');
  pdfPreviewFrame.src = '';
};

// Retry Action
window.retryFailedJob = async function () {
  if (!state.activeJobId) return;
  retryFailedBtn.disabled = true;

  try {
    const res = await fetch(`/api/v1/jobs/${state.activeJobId}/retry`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Retry failed');
    }
    showToast('Retrying failed certificates in background...', 'info');
    startPolling(state.activeJobId);
  } catch (err) {
    showToast(`Retry error: ${err.message}`, 'error');
  } finally {
    retryFailedBtn.disabled = false;
  }
};

// Toast Notifications
function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${escapeHtml(message)}</span>`;
  toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Utility: Escape HTML
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
