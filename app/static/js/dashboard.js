document.addEventListener('DOMContentLoaded', () => {
  const rawDataElem = document.getElementById('appData');
  if (!rawDataElem) return;

  const data = JSON.parse(rawDataElem.textContent);
  if (!data || data.length === 0) return;

  const approvedCount = data.filter(d => d.prediction.status === 'Approved').length;
  const rejectedCount = data.length - approvedCount;

  new Chart(document.getElementById('approvalChart'), {
    type: 'doughnut',
    data: {
      labels: ['Approved', 'Rejected'],
      datasets: [{
        data: [approvedCount, rejectedCount],
        backgroundColor: ['#2E5A44', '#E07A5F'],
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom' } }
    }
  });

  const purposeCounts = {};
  data.forEach(d => {
    const p = d.applicant_data.Loan_Purpose || 'Other';
    purposeCounts[p] = (purposeCounts[p] || 0) + 1;
  });

  new Chart(document.getElementById('purposeChart'), {
    type: 'bar',
    data: {
      labels: Object.keys(purposeCounts),
      datasets: [{
        label: 'Applications',
        data: Object.values(purposeCounts),
        backgroundColor: '#7A9A8B',
        borderRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: { y: { beginAtZero: true } },
      plugins: { legend: { display: false } }
    }
  });
});