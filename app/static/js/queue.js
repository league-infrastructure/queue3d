async function updateJob(jobId, data) {
    try {
        const resp = await fetch(`/api/jobs/${jobId}`, {
            method: 'PATCH',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data),
        });
        if (resp.ok) {
            // Reload the card via HTMX partial
            const cardResp = await fetch(`/api/partials/queue-card/${jobId}`);
            if (cardResp.ok) {
                const html = await cardResp.text();
                const card = document.getElementById(`job-${jobId}`);
                if (card) {
                    card.outerHTML = html;
                    // Re-init STL viewers for the new card
                    if (window.initSTLViewers) window.initSTLViewers();
                }
            }
        } else {
            const err = await resp.json();
            alert(err.detail || 'Error updating job');
        }
    } catch (e) {
        alert('Network error: ' + e.message);
    }
}

async function rejectJob(jobId) {
    const reason = prompt('Enter rejection reason:');
    if (reason === null) return; // cancelled
    await updateJob(jobId, {status: 'rejected', reject_reason: reason});
}

async function deleteJob(jobId) {
    if (!confirm('Delete this job and its file? This cannot be undone.')) return;
    try {
        const resp = await fetch(`/api/jobs/${jobId}`, {method: 'DELETE'});
        if (resp.ok) {
            const card = document.getElementById(`job-${jobId}`);
            if (card) card.remove();
        } else {
            const err = await resp.json();
            alert(err.detail || 'Error deleting job');
        }
    } catch (e) {
        alert('Network error: ' + e.message);
    }
}

async function openJobModal(jobId) {
    const modal = document.getElementById('job-modal');
    const content = document.getElementById('job-modal-content');
    try {
        const resp = await fetch(`/api/partials/job-modal/${jobId}`);
        if (resp.ok) {
            content.innerHTML = await resp.text();
            modal.showModal();
            // Init STL viewer in the modal
            if (window.initSTLViewers) window.initSTLViewers();
        }
    } catch (e) {
        alert('Error loading job details');
    }
}

function filterQueue() {
    const statusSelect = document.getElementById('status-filter');
    const locationSelect = document.getElementById('location-filter');
    const status = statusSelect ? statusSelect.value : '';
    const locationId = locationSelect ? locationSelect.value : '';

    // Update URL params so filters persist on refresh
    const url = new URL(window.location);
    if (status) url.searchParams.set('status', status);
    else url.searchParams.delete('status');
    if (locationId) url.searchParams.set('location', locationId);
    else url.searchParams.delete('location');
    history.replaceState(null, '', url);

    // Apply client-side filtering
    const cards = document.querySelectorAll('.queue-card');
    cards.forEach(card => {
        const statusMatch = !status || card.dataset.status === status;
        const locationMatch = !locationId || card.dataset.locationId === locationId;
        card.style.display = (statusMatch && locationMatch) ? '' : 'none';
    });
}

// Restore filter selections from URL params on page load
function restoreFilters() {
    const params = new URLSearchParams(window.location.search);
    const status = params.get('status') || '';
    const locationId = params.get('location') || '';

    const statusSelect = document.getElementById('status-filter');
    const locationSelect = document.getElementById('location-filter');

    if (statusSelect && status) statusSelect.value = status;
    if (locationSelect && locationId) locationSelect.value = locationId;

    // Apply filters if any are set
    if (status || locationId) filterQueue();
}

// --- Auto-refresh polling (every 5 seconds) ---
let lastQueueHash = null;

async function computeQueueHash() {
    try {
        const scope = window.queueScope || '';
        const url = scope ? `/api/jobs?scope=${scope}` : '/api/jobs';
        const resp = await fetch(url);
        if (!resp.ok) return null;
        const jobs = await resp.json();
        // Build a simple hash from job ids, statuses, and feedback
        return jobs.map(j => `${j.id}:${j.status}:${j.feedback || ''}:${j.fail_count || 0}`).join('|');
    } catch {
        return null;
    }
}

async function pollForUpdates() {
    const newHash = await computeQueueHash();
    if (newHash === null) return; // request failed, skip

    if (lastQueueHash === null) {
        // First poll — record the baseline, don't refresh
        lastQueueHash = newHash;
        return;
    }

    if (newHash !== lastQueueHash) {
        lastQueueHash = newHash;
        window.location.reload();
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    restoreFilters();
    // First poll fetches from API to set the baseline; subsequent polls compare
    pollForUpdates();
    setInterval(pollForUpdates, 5000);
});
