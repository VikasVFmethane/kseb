
// Enhanced version of the demand_visualization.js file with fixes

document.addEventListener('DOMContentLoaded', () => {
    // Configuration
    const unitFactors = {
        TWh: 1000000000,
        GWh: 1000000,
        MWh: 1000,
        kWh: 1
    };
    const modelColors = {
        MLR: 'rgba(75, 192, 192, 0.7)',
        SLR: 'rgba(255, 99, 132, 0.7)',
        TimeSeries: 'rgba(54, 162, 235, 0.7)',
        WAM: 'rgba(255, 206, 86, 0.7)',
        'User Data': 'rgba(153, 102, 255, 0.7)'  // Color for User Data
    };
    const defaultModels = ['MLR', 'SLR', 'TimeSeries', 'WAM', 'User Data'];

    // State
    let currentSector = 'consolidated';
    let currentScenario = document.getElementById('scenarioSelect').value;
    let currentUnit = 'TWh';
    let yearRange = {
        from: parseInt(document.getElementById('fromYear').value),
        to: parseInt(document.getElementById('toYear').value)
    };
    let sectorData = {};
    let sectorModels = {};  // Store available models per sector
    let charts = {};
    let comparisonScenarios = { consolidated: '' };
    let comparisonData = {}; // Store data for comparison scenarios

    // Initialize
    initializeEventListeners();
    loadForecastData(currentScenario);

    function initializeEventListeners() {
        // Sector navigation
        document.querySelectorAll('.sector-button').forEach(button => {
            button.addEventListener('click', () => {
                switchSector(button.dataset.sector);
            });
        });

        // View toggle
        document.querySelectorAll('.view-toggle-button').forEach(button => {
            button.addEventListener('click', () => {
                switchView(button.dataset.sector, button.dataset.view);
            });
        });

        // Chart type toggle
        document.querySelectorAll('.chart-type-controls .btn').forEach(button => {
            button.addEventListener('click', () => {
                document.querySelectorAll('.chart-type-controls .btn').forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');
                updateView('consolidated', 'chart');
            });
        });

        // Settings
        document.getElementById('scenarioSelect').addEventListener('change', (e) => {
            currentScenario = e.target.value;
            loadForecastData(currentScenario);
        });

        document.getElementById('unitSelect').addEventListener('change', (e) => {
            currentUnit = e.target.value;
            updateAllViews();
        });

        document.getElementById('fromYear').addEventListener('change', (e) => {
            yearRange.from = parseInt(e.target.value);
            if (yearRange.from > yearRange.to) {
                yearRange.to = yearRange.from;
                document.getElementById('toYear').value = yearRange.to;
            }
            updateAllViews();
        });

        document.getElementById('toYear').addEventListener('change', (e) => {
            yearRange.to = parseInt(e.target.value);
            if (yearRange.to < yearRange.from) {
                yearRange.from = yearRange.to;
                document.getElementById('fromYear').value = yearRange.from;
            }
            updateAllViews();
        });

        // Sector model selection
        document.querySelectorAll('.sector-model-select').forEach(select => {
            select.addEventListener('change', () => {
                updateAllViews();
            });
        });

        // Scenario comparison dropdowns
        document.querySelectorAll('[id^="compareScenario"]').forEach(select => {
            select.addEventListener('change', (e) => {
                const sector = select.dataset.sector;
                comparisonScenarios[sector] = e.target.value;
                if (e.target.value) {
                    // Load comparison data if not already loaded
                    if (!comparisonData[e.target.value]) {
                        loadComparisonData(e.target.value, sector);
                    } else {
                        updateComparisonContainerWidth(sector);
                        updateScenarioComparison(sector, e.target.value);
                    }
                } else {
                    updateComparisonContainerWidth(sector);
                    updateScenarioComparison(sector, '');
                }
            });
        });

        // Download buttons
        document.getElementById('downloadConsolidated').addEventListener('click', () => {
            downloadCSV('consolidated', currentScenario);
        });

        document.getElementById('downloadChartConsolidated').addEventListener('click', () => {
            downloadChart('consolidatedChart', `Consolidated_Chart_${currentScenario}`);
        });

        document.getElementById('downloadComparisonConsolidated').addEventListener('click', () => {
            downloadComparison('consolidated');
        });

        document.querySelectorAll('[id^="download"]').forEach(button => {
            const id = button.id;
            if (id.startsWith('download') && !id.includes('Consolidated')) {
                const sector = id.replace('download', '').replace('Chart', '').replace('Comparison', '');
                if (id.includes('Chart')) {
                    button.addEventListener('click', () => {
                        downloadChart(`${sector}Chart`, `${sector}_Chart_${currentScenario}`);
                    });
                } else if (id.includes('Comparison')) {
                    button.addEventListener('click', () => {
                        downloadComparison(sector);
                    });
                } else {
                    button.addEventListener('click', () => {
                        downloadCSV(sector, currentScenario);
                    });
                }
            }
        });
    }

    function downloadCSV(sector, scenario) {
        const params = new URLSearchParams({
            unit: currentUnit,
            from_year: yearRange.from,
            to_year: yearRange.to
        });
        if (sector === 'consolidated') {
            document.querySelectorAll('.sector-model-select').forEach(select => {
                params.append(`model_${select.dataset.sector}`, select.value);
            });
        }
        if (comparisonScenarios[sector]) {
            params.append('compare_scenario', comparisonScenarios[sector]);
        }

        fetch(`/demand/api/download_csv/${scenario}/${sector}?${params.toString()}`)
            .then(response => {
                if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
                return response.blob();
            })
            .then(blob => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `${scenario}_${sector}_data_${new Date().toISOString().replace(/[:.]/g, '-')}.csv`;
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(url);
                showNotification('success', 'CSV downloaded successfully');
            })
            .catch(error => {
                console.error('Error downloading CSV:', error);
                showNotification('danger', `Failed to download CSV: ${error.message}`);
            });
    }

    function downloadChart(chartId, filename) {
        const canvas = document.getElementById(chartId);
        if (!canvas || !charts[chartId]) {
            showNotification('danger', 'Chart not available for download');
            return;
        }
        const a = document.createElement('a');
        a.href = charts[chartId].toBase64Image();
        a.download = `${filename}_${new Date().toISOString().replace(/[:.]/g, '-')}.png`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        showNotification('success', 'Chart downloaded successfully');
    }

    function downloadComparison(sector) {
        downloadCSV(sector, currentScenario);
        downloadChart(`${sector}ComparisonChart1`, `${sector}_Comparison_${currentScenario}`);
        if (comparisonScenarios[sector]) {
            downloadChart(`${sector}ComparisonChart2`, `${sector}_Comparison_${comparisonScenarios[sector]}`);
        }
    }

    function updateComparisonContainerWidth(sector) {
        const container = document.getElementById(`${sector}-comparison-container`);
        if (!container) return;
        const chart2 = document.getElementById(`${sector}-comparison-chart2`);
        if (comparisonScenarios[sector]) {
            container.classList.add('split');
            if(chart2) chart2.style.display = 'block';
        } else {
            container.classList.remove('split');
            if(chart2) chart2.style.display = 'none';
        }
    }


    async function loadForecastData(scenario) {
        try {
            console.log('Loading forecast data for scenario:', scenario);
            const response = await fetch(`/demand/api/forecast_data/${scenario}`, {
                headers: { 'Accept': 'application/json' }
            });
            console.log('API response status:', response.status);
            if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
            
            const result = await response.json();
            console.log('API response data:', result);
            
            if (result.status !== 'success') {
                 // Even if status is not 'success', there might be a message
                throw new Error(result.message || 'Failed to load forecast data (unknown error)');
            }

            if (!result.data || Object.keys(result.data).length === 0) {
                sectorData = {}; // Ensure it's an empty object
                let errorMessage = result.message || 'Backend Error: No sector data could be processed. This might be due to issues with input files or backend processing. Please check server logs.';
                showNotification('danger', errorMessage, 15000);
                updateYearDropdowns(); 
                updateAllViews(); 
                return; 
            }

            sectorData = result.data;

            // Initialize sectorModels and update sidebar dropdowns
            sectorModels = {};
            Object.keys(sectorData).forEach(sector => {
                sectorModels[sector] = sectorData[sector].models || ['WAM']; // Default to WAM if models array is missing
                updateModelDropdown(sector);
            });

            updateYearDropdowns();
            comparisonScenarios = { consolidated: '' };
            document.querySelectorAll('[id^="compareScenario"]').forEach(select => {
                const sectorForSelect = select.dataset.sector;
                select.value = '';
                comparisonScenarios[sectorForSelect] = '';
                updateComparisonContainerWidth(sectorForSelect);
            });
            updateAllViews();
        } catch (error) {
            console.error('Error loading forecast data:', error);
            showNotification('danger', `Failed to load forecast data: ${error.message}`, 15000);
            sectorData = {}; // Reset data on error
            updateYearDropdowns(); // Attempt to update UI to reflect no data
            updateAllViews();
        }
    }

    async function loadComparisonData(scenario, sector) {
        try {
            console.log('Loading comparison data for scenario:', scenario);
            const response = await fetch(`/demand/api/forecast_data/${scenario}`, {
                headers: { 'Accept': 'application/json' }
            });
             if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
            const result = await response.json();
            if (result.status !== 'success') throw new Error(result.message || 'Failed to load comparison data');

            if (!result.data || Object.keys(result.data).length === 0) {
                 showNotification('warning', `No data found for comparison scenario: ${scenario}.`, 10000);
                 comparisonData[scenario] = {}; // Store empty to avoid re-fetching
            } else {
                comparisonData[scenario] = result.data;
            }
            updateComparisonContainerWidth(sector);
            updateScenarioComparison(sector, scenario);
        } catch (error) {
            console.error('Error loading comparison data:', error);
            showNotification('danger', `Failed to load comparison data for ${scenario}: ${error.message}`, 10000);
        }
    }

    function updateModelDropdown(sector) {
        const select = document.querySelector(`.sector-model-select[data-sector="${sector}"]`);
        if (!select) return;
        const models = sectorModels[sector] || ['WAM'];
        select.innerHTML = models.map(model => `<option value="${model}">${model}</option>`).join('');
        select.value = models.includes('User Data') ? 'User Data' : models.includes('WAM') ? 'WAM' : models[0];
    }

    function updateYearDropdowns() {
        const fromYearSelect = document.getElementById('fromYear');
        const toYearSelect = document.getElementById('toYear');
        let allYears = new Set();

        if (sectorData && Object.keys(sectorData).length > 0) {
            Object.values(sectorData).forEach(data => {
                if (data && data.years && Array.isArray(data.years)) {
                    data.years.forEach(year => allYears.add(year));
                }
            });
        }
        
        allYears = Array.from(allYears).sort((a, b) => a - b);
        
        fromYearSelect.innerHTML = ''; // Clear previous options
        toYearSelect.innerHTML = '';   // Clear previous options

        if (allYears.length === 0) {
            console.warn('No valid years found in API data. This might be due to backend processing errors.');
            showNotification('warning', 'No date range available. Data might be missing or corrupted.', 10000);
            fromYearSelect.innerHTML = '<option value="">N/A</option>';
            toYearSelect.innerHTML = '<option value="">N/A</option>';
            fromYearSelect.disabled = true;
            toYearSelect.disabled = true;
            yearRange = { from: null, to: null }; // Reset year range
            return;
        }

        fromYearSelect.disabled = false;
        toYearSelect.disabled = false;

        allYears.forEach(year => {
            const optionFrom = document.createElement('option');
            optionFrom.value = year;
            optionFrom.textContent = year;
            fromYearSelect.appendChild(optionFrom);
            
            const optionTo = document.createElement('option');
            optionTo.value = year;
            optionTo.textContent = year;
            toYearSelect.appendChild(optionTo);
        });

        // Try to set previous yearRange or default to available min/max
        yearRange.from = allYears.includes(yearRange.from) ? yearRange.from : allYears[0];
        yearRange.to = allYears.includes(yearRange.to) ? yearRange.to : allYears[allYears.length - 1];
        
        // Ensure from <= to
        if(yearRange.from > yearRange.to) yearRange.from = yearRange.to;

        fromYearSelect.value = yearRange.from;
        toYearSelect.value = yearRange.to;
    }

    function switchSector(sector) {
        currentSector = sector;
        document.querySelectorAll('.sector-button').forEach(btn => btn.classList.remove('active'));
        const activeBtn = document.querySelector(`.sector-button[data-sector="${sector}"]`);
        if (activeBtn) activeBtn.classList.add('active');
        
        document.querySelectorAll('.sector-section').forEach(section => section.classList.remove('active'));
        const activeSection = document.getElementById(`${sector}-section`);
        if (activeSection) activeSection.classList.add('active');
        
        updateAllViews();
    }

    function switchView(sector, view) {
        document.querySelectorAll(`.view-toggle-button[data-sector="${sector}"]`).forEach(btn => btn.classList.remove('active'));
        const activeToggleBtn = document.querySelector(`.view-toggle-button[data-sector="${sector}"][data-view="${view}"]`);
        if (activeToggleBtn) activeToggleBtn.classList.add('active');

        document.querySelectorAll(`#${sector}-section .view-content`).forEach(content => content.style.display = 'none');
        const activeViewContent = document.getElementById(`${sector}-${view}-view`);
        if (activeViewContent) activeViewContent.style.display = 'flex';
        
        const controls = document.querySelector(`#${sector}-section .scenario-comparison-controls`);
        if (controls) {
            controls.classList.toggle('hidden', view !== 'comparison');
        }
        updateView(sector, view);
    }

    function updateAllViews() {
        const activeView = document.querySelector(`.view-toggle-button[data-sector="${currentSector}"].active`)?.dataset.view || 'table';
        updateView(currentSector, activeView);
    }

    function updateView(sector, view) {
        const sectorViewElement = document.getElementById(`${sector}-section`);

        if (sector !== 'consolidated' && (!sectorData || !sectorData[sector] || !sectorData[sector].years)) {
            showNotification('warning', `No data available for sector: ${sector}. Please check backend processing.`, 8000);
            if (sectorViewElement) {
                // Clear previous content or show specific message for this sector
                const tableContainer = sectorViewElement.querySelector('.table-container');
                if (tableContainer) tableContainer.innerHTML = '<p class="text-muted p-3">No data available for this sector.</p>';
                
                const chartCanvasId = `${sector}Chart`;
                const chartCanvas = document.getElementById(chartCanvasId);
                if (chartCanvas) {
                    if (charts[chartCanvasId]) {
                        charts[chartCanvasId].destroy();
                        delete charts[chartCanvasId];
                    }
                    const ctx = chartCanvas.getContext('2d');
                    ctx.clearRect(0, 0, chartCanvas.width, chartCanvas.height);
                    ctx.font = "16px Arial";
                    ctx.textAlign = "center";
                    ctx.fillText("No data available.", chartCanvas.width / 2, chartCanvas.height / 2);
                }

                const comparisonContainerId = `${sector}-comparison-container`;
                const comparisonContainer = document.getElementById(comparisonContainerId);
                if(comparisonContainer) comparisonContainer.innerHTML = '<p class="text-muted p-3">No data available for comparison.</p>';

                // Hide loading spinners if any are visible for this sector
                const loadingSpinners = sectorViewElement.querySelectorAll('.table-loading, .chart-loading');
                loadingSpinners.forEach(spinner => spinner.style.display = 'none');
            }
            return;
        }

        // Show loading indicator for the specific view
        const viewElement = document.getElementById(`${sector}-${view}-view`);
        if (viewElement) {
            const loadingEl = viewElement.querySelector('.table-loading, .chart-loading');
            if (loadingEl) loadingEl.style.display = 'block';
        }


        if (sector === 'consolidated') {
            if (view === 'table') updateConsolidatedTable();
            else if (view === 'chart') updateConsolidatedChart();
            else if (view === 'comparison') updateScenarioComparison(sector, comparisonScenarios[sector] || '');
        } else {
            if (view === 'table') updateSectorTable(sector);
            else if (view === 'chart') updateSectorChart(sector);
            else if (view === 'comparison') updateScenarioComparison(sector, comparisonScenarios[sector] || '');
        }
    }

    function updateConsolidatedTable() {
        const tableBody = document.querySelector('#consolidatedTable tbody');
        const loadingEl = document.querySelector('#consolidated-table-view .table-loading');
        if (!tableBody) return;
        tableBody.innerHTML = '';
        
        if (loadingEl) loadingEl.style.display = 'block';

        if (!sectorData || Object.keys(sectorData).length === 0) {
            tableBody.innerHTML = '<tr><td colspan="100%" class="text-center text-muted">No data available to display.</td></tr>';
            if (loadingEl) loadingEl.style.display = 'none';
            return;
        }
        
        const years = new Set();
        const dataByYear = {};

        Object.keys(sectorData).forEach(sector => {
            const select = document.querySelector(`.sector-model-select[data-sector="${sector}"]`);
            const model = select ? select.value : (sectorModels[sector] && sectorModels[sector].includes('User Data') ? 'User Data' : 'WAM');
            const data = sectorData[sector];
            if (!data || !data.years || !data[model]) {
                console.warn(`Missing data for sector ${sector}, model ${model}`);
                return;
            }
            data.years.forEach((year, i) => {
                if (year >= yearRange.from && year <= yearRange.to) {
                    years.add(year);
                    if (!dataByYear[year]) dataByYear[year] = {};
                    dataByYear[year][sector] = (data[model][i] || 0) / unitFactors[currentUnit];
                }
            });
        });

        Array.from(years).sort((a, b) => a - b).forEach(year => {
            const row = document.createElement('tr');
            row.innerHTML = `<td>${year}</td>`;
            let total = 0;
            Object.keys(sectorData).forEach(sector => {
                const value = dataByYear[year] && dataByYear[year][sector] !== undefined ? dataByYear[year][sector] : 0;
                row.innerHTML += `<td class="numeric">${value.toFixed(2)}</td>`;
                total += value;
            });
            row.innerHTML += `<td class="numeric fw-bold">${total.toFixed(2)}</td>`;
            tableBody.appendChild(row);
        });

        if (loadingEl) loadingEl.style.display = 'none';
    }

    function updateConsolidatedChart() {
        const canvas = document.getElementById('consolidatedChart');
        const loadingEl = document.querySelector('#consolidated-chart-view .chart-loading'); // Might not exist, handle null
        const chartType = document.querySelector('.chart-type-controls .btn.active')?.dataset.chartType || 'area';
        
        if (loadingEl) loadingEl.style.display = 'block';

        if (!sectorData || Object.keys(sectorData).length === 0) {
            if (charts.consolidatedChart) charts.consolidatedChart.destroy();
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0,0,canvas.width, canvas.height);
            ctx.fillText("No data to display chart.", canvas.width/2, canvas.height/2);
            if (loadingEl) loadingEl.style.display = 'none';
            return;
        }

        const datasets = [];
        const allYears = new Set();

        Object.keys(sectorData).forEach(sector => {
            const data = sectorData[sector];
            if (!data || !data.years) return;
            data.years.forEach(year => {
                if (year >= yearRange.from && year <= yearRange.to) allYears.add(year);
            });
        });

        const years = Array.from(allYears).sort((a, b) => a - b);

        Object.keys(sectorData).forEach((sector, i) => {
            const select = document.querySelector(`.sector-model-select[data-sector="${sector}"]`);
            const model = select ? select.value : (sectorModels[sector] && sectorModels[sector].includes('User Data') ? 'User Data' : 'WAM');
            const data = sectorData[sector];
            if (!data || !data.years || !data[model]) return;

            const filteredData = years.map(year => {
                const index = data.years.indexOf(year);
                return index !== -1 ? (data[model][index] || 0) / unitFactors[currentUnit] : 0;
            });

            datasets.push({
                label: sector,
                data: filteredData,
                backgroundColor: `rgba(${(i * 50) % 255}, ${(i * 100) % 255}, ${(i * 150) % 255}, 0.7)`,
                borderColor: `rgba(${(i * 50) % 255}, ${(i * 100) % 255}, ${(i * 150) % 255}, 1)`,
                fill: chartType === 'area'
            });
        });

        if (charts.consolidatedChart) charts.consolidatedChart.destroy();
        charts.consolidatedChart = new Chart(canvas, {
            type: chartType === 'area' ? 'line' : chartType,
            data: { labels: years, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true, title: { display: true, text: currentUnit }, ticks: { callback: value => Number.isFinite(value) ? value.toFixed(2) : value } },
                    x: { title: { display: true, text: 'Year' } }
                },
                plugins: {
                    legend: { position: 'top' },
                    tooltip: {
                        callbacks: {
                            label: context => {
                                const value = context.parsed.y;
                                return `${context.dataset.label}: ${Number.isFinite(value) ? value.toFixed(2) : 'N/A'} ${currentUnit}`;
                            }
                        }
                    }
                }
            }
        });

        if (loadingEl) loadingEl.style.display = 'none';
    }

    function updateSectorTable(sector) {
        const tableBody = document.querySelector(`#${sector}Table tbody`);
        const loadingEl = document.querySelector(`#${sector}-table-view .table-loading`);
        if (!tableBody) return;
        tableBody.innerHTML = '';

        if (loadingEl) loadingEl.style.display = 'block';

        const data = sectorData[sector];
        if (!data || !data.years) {
            tableBody.innerHTML = '<tr><td colspan="100%" class="text-center text-muted">No data available for this sector.</td></tr>';
            if (loadingEl) loadingEl.style.display = 'none';
            return;
        }
        const models = sectorModels[sector] || ['WAM'];
        const tableHead = document.querySelector(`#${sector}Table thead tr`);
        if (tableHead) tableHead.innerHTML = `<th>Year</th>` + models.map(model => `<th>${model}</th>`).join('');
        
        data.years.forEach((year, i) => {
            if (year >= yearRange.from && year <= yearRange.to) {
                const row = document.createElement('tr');
                row.innerHTML = `<td>${year}</td>`;
                models.forEach(model => {
                    const value = (data[model] && data[model][i] !== undefined ? data[model][i] : 0) / unitFactors[currentUnit];
                    row.innerHTML += `<td class="numeric">${Number.isFinite(value) ? value.toFixed(2) : 'N/A'}</td>`;
                });
                tableBody.appendChild(row);
            }
        });
        if (loadingEl) loadingEl.style.display = 'none';
    }

    function updateSectorChart(sector) {
        const canvas = document.getElementById(`${sector}Chart`);
        const loadingEl = document.querySelector(`#${sector}-chart-view .chart-loading`); // Might not exist
        if (!canvas) return;

        if (loadingEl) loadingEl.style.display = 'block';
        
        const data = sectorData[sector];
        if (!data || !data.years) {
            if (charts[`${sector}Chart`]) charts[`${sector}Chart`].destroy();
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0,0,canvas.width, canvas.height);
            ctx.fillText("No data to display chart.", canvas.width/2, canvas.height/2);
            if (loadingEl) loadingEl.style.display = 'none';
            return;
        }
        const models = sectorModels[sector] || ['WAM'];
        const years = data.years.filter(year => year >= yearRange.from && year <= yearRange.to);
        const datasets = models.map(model => ({
            label: model,
            data: data.years.map((year, i) => {
                if (year >= yearRange.from && year <= yearRange.to) {
                    return (data[model] && data[model][i] !== undefined ? data[model][i] : 0) / unitFactors[currentUnit];
                }
                return null;
            }).filter(v => v !== null),
            backgroundColor: modelColors[model] || 'rgba(128, 128, 128, 0.7)',
            borderColor: (modelColors[model] || 'rgba(128, 128, 128, 0.7)').replace('0.7', '1'),
            fill: false,
            tension: 0.1
        }));

        if (charts[`${sector}Chart`]) charts[`${sector}Chart`].destroy();
        charts[`${sector}Chart`] = new Chart(canvas, {
            type: 'line',
            data: { labels: years, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true, title: { display: true, text: currentUnit }, ticks: { callback: value => Number.isFinite(value) ? value.toFixed(2) : value } },
                    x: { title: { display: true, text: 'Year' } }
                },
                plugins: {
                    legend: { position: 'top' },
                    tooltip: {
                        callbacks: {
                            label: context => {
                                const value = context.parsed.y;
                                return `${context.dataset.label}: ${Number.isFinite(value) ? value.toFixed(2) : 'N/A'} ${currentUnit}`;
                            }
                        }
                    }
                }
            }
        });

        if (loadingEl) loadingEl.style.display = 'none';
    }

    async function updateScenarioComparison(sector, compareScenario) {
        const isConsolidated = sector === 'consolidated';
        const canvas1 = document.getElementById(`${sector}ComparisonChart1`);
        const canvas2 = document.getElementById(`${sector}ComparisonChart2`);
        const loadingEl = document.querySelector(`#${sector}-comparison-view .chart-loading`); // Generic loader for the view
        
        if (loadingEl) loadingEl.style.display = 'block';

        if (!canvas1 || (!compareScenario && !canvas2)) { // If no comparison, canvas2 might not be strictly needed
            if (loadingEl) loadingEl.style.display = 'none';
            return;
        }

        // For the primary scenario (current scenario)
        let data1 = isConsolidated ? aggregateSectorData(sectorData) : sectorData[sector];
        let data2 = null;

        if (!data1 || !data1.years) {
            showNotification('warning', `No data available for ${currentScenario} in ${sector} sector for comparison.`, 8000);
            if (charts[`${sector}ComparisonChart1`]) charts[`${sector}ComparisonChart1`].destroy();
            const ctx1 = canvas1.getContext('2d');
            ctx1.clearRect(0,0,canvas1.width, canvas1.height);
            ctx1.fillText("No data available.", canvas1.width/2, canvas1.height/2);
            if (canvas2) {
                if (charts[`${sector}ComparisonChart2`]) charts[`${sector}ComparisonChart2`].destroy();
                const ctx2 = canvas2.getContext('2d');
                ctx2.clearRect(0,0,canvas2.width, canvas2.height);
            }
            if (loadingEl) loadingEl.style.display = 'none';
            return;
        }

        if (compareScenario) {
            try {
                let comparisonScenarioData = comparisonData[compareScenario];
                if (!comparisonScenarioData) {
                    const response = await fetch(`/demand/api/forecast_data/${compareScenario}`, {
                        headers: { 'Accept': 'application/json' }
                    });
                    if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
                    const result = await response.json();
                    if (result.status !== 'success' || !result.data || Object.keys(result.data).length === 0) {
                         throw new Error(result.message || `No data found for scenario ${compareScenario}`);
                    }
                    comparisonData[compareScenario] = result.data;
                    comparisonScenarioData = result.data;
                }
                
                data2 = isConsolidated ?
                    aggregateSectorData(comparisonScenarioData, true) :
                    comparisonScenarioData[sector];

                if (!data2 || !data2.years) {
                    throw new Error(`No data for ${sector} sector in comparison scenario ${compareScenario}.`);
                }
                if (data2.models) {
                    sectorModels[`${sector}_compare`] = data2.models;
                }

            } catch (error) {
                console.error('Error loading comparison scenario:', error);
                showNotification('danger', `Failed to load comparison scenario ${compareScenario}: ${error.message}`, 10000);
                data2 = null; 
            }
        }

        const years1 = data1.years.filter(year => year >= yearRange.from && year <= yearRange.to);
        let datasets1 = [];

        if (isConsolidated) {
            Object.keys(sectorData).forEach((sectorName, i) => {
                const select = document.querySelector(`.sector-model-select[data-sector="${sectorName}"]`);
                const selectedModel = select ? select.value : (sectorModels[sectorName] && sectorModels[sectorName].includes('User Data') ? 'User Data' : 'WAM');
                if (data1[sectorName] && data1[sectorName][selectedModel]) { // Check model exists
                    datasets1.push({
                        label: sectorName,
                        data: years1.map(year => {
                            const yearIndex = data1.years.indexOf(year);
                            return yearIndex !== -1 && data1[sectorName][selectedModel][yearIndex] !== undefined ? (data1[sectorName][selectedModel][yearIndex] || 0) / unitFactors[currentUnit] : 0;
                        }),
                        backgroundColor: `rgba(${(i * 50) % 255}, ${(i * 100) % 255}, ${(i * 150) % 255}, 0.7)`,
                        borderColor: `rgba(${(i * 50) % 255}, ${(i * 100) % 255}, ${(i * 150) % 255}, 1)`,
                        fill: false, tension: 0.1
                    });
                }
            });
        } else {
            const models1 = sectorModels[sector] || ['WAM'];
            datasets1 = models1.map(model => ({
                label: model,
                data: data1.years.map((year, i) => {
                    if (year >= yearRange.from && year <= yearRange.to) {
                        return (data1[model] && data1[model][i] !== undefined ? data1[model][i] : 0) / unitFactors[currentUnit];
                    }
                    return null;
                }).filter(v => v !== null),
                backgroundColor: modelColors[model] || 'rgba(128, 128, 128, 0.7)',
                borderColor: (modelColors[model] || 'rgba(128, 128, 128, 0.7)').replace('0.7', '1'),
                fill: false, tension: 0.1
            }));
        }

        if (charts[`${sector}ComparisonChart1`]) charts[`${sector}ComparisonChart1`].destroy();
        charts[`${sector}ComparisonChart1`] = new Chart(canvas1, {
            type: 'line', data: { labels: years1, datasets: datasets1 },
            options: { responsive: true, maintainAspectRatio: false,
                scales: { y: { beginAtZero: true, title: { display: true, text: currentUnit }, ticks: { callback: value => Number.isFinite(value) ? value.toFixed(2) : value } }, x: { title: { display: true, text: 'Year' } } },
                plugins: { title: { display: true, text: currentScenario, font: { size: 14 } }, legend: { position: 'top' }, tooltip: { callbacks: { label: context => `${context.dataset.label}: ${Number.isFinite(context.parsed.y) ? context.parsed.y.toFixed(2) : 'N/A'} ${currentUnit}` } } }
            }
        });

        if (canvas2) { // Only proceed if canvas2 exists
            if (data2) {
                const years2 = data2.years.filter(year => year >= yearRange.from && year <= yearRange.to);
                let datasets2 = [];
                if (isConsolidated) {
                    Object.keys(comparisonData[compareScenario]).forEach((sectorName, i) => {
                        const select = document.querySelector(`.sector-model-select[data-sector="${sectorName}"]`); // Use same model selection for simplicity or add separate controls
                        const selectedModel = select ? select.value : (sectorModels[`${sectorName}_compare`] && sectorModels[`${sectorName}_compare`].includes('User Data') ? 'User Data' : 'WAM');
                        if (data2[sectorName] && data2[sectorName][selectedModel]) {
                             datasets2.push({
                                label: sectorName,
                                data: years2.map(year => {
                                    const yearIndex = data2.years.indexOf(year);
                                    return yearIndex !== -1 && data2[sectorName][selectedModel][yearIndex] !== undefined ? (data2[sectorName][selectedModel][yearIndex] || 0) / unitFactors[currentUnit] : 0;
                                }),
                                backgroundColor: `rgba(${(i * 50) % 255}, ${(i * 100) % 255}, ${(i * 150) % 255}, 0.5)`,
                                borderColor: `rgba(${(i * 50) % 255}, ${(i * 100) % 255}, ${(i * 150) % 255}, 0.8)`,
                                fill: false, tension: 0.1
                            });
                        }
                    });
                } else {
                    const models2 = sectorModels[`${sector}_compare`] || sectorModels[sector] || ['WAM'];
                    datasets2 = models2.map(model => ({
                        label: model,
                        data: data2.years.map((year, i) => {
                            if (year >= yearRange.from && year <= yearRange.to) {
                                return (data2[model] && data2[model][i] !== undefined ? data2[model][i] : 0) / unitFactors[currentUnit];
                            }
                            return null;
                        }).filter(v => v !== null),
                        backgroundColor: (modelColors[model] || 'rgba(128, 128, 128, 0.5)').replace('0.7', '0.5'),
                        borderColor: (modelColors[model] || 'rgba(128, 128, 128, 0.8)').replace('0.7', '0.8'),
                        fill: false, tension: 0.1
                    }));
                }

                if (charts[`${sector}ComparisonChart2`]) charts[`${sector}ComparisonChart2`].destroy();
                charts[`${sector}ComparisonChart2`] = new Chart(canvas2, {
                    type: 'line', data: { labels: years2, datasets: datasets2 },
                    options: { responsive: true, maintainAspectRatio: false,
                        scales: { y: { beginAtZero: true, title: { display: true, text: currentUnit }, ticks: { callback: value => Number.isFinite(value) ? value.toFixed(2) : value } }, x: { title: { display: true, text: 'Year' } } },
                        plugins: { title: { display: true, text: compareScenario, font: { size: 14 } }, legend: { position: 'top' }, tooltip: { callbacks: { label: context => `${context.dataset.label}: ${Number.isFinite(context.parsed.y) ? context.parsed.y.toFixed(2) : 'N/A'} ${currentUnit}` } } }
                    }
                });
            } else {
                if (charts[`${sector}ComparisonChart2`]) charts[`${sector}ComparisonChart2`].destroy();
                const ctx = canvas2.getContext('2d');
                ctx.clearRect(0, 0, canvas2.width, canvas2.height);
                if(compareScenario) { // Only show "no data" if a comparison scenario was selected but failed to load
                     ctx.font = "16px Arial";
                     ctx.textAlign = "center";
                     ctx.fillText(`No data for ${compareScenario}.`, canvas2.width / 2, canvas2.height / 2);
                }
            }
        }
        if (loadingEl) loadingEl.style.display = 'none';
    }

    function aggregateSectorData(dataInput, isComparison = false) {
        const years = new Set();
        const aggregated = {};
        const sourceModels = isComparison ? sectorModels : sectorModels; // Use main models for comparison logic for now

        Object.keys(dataInput).forEach(sector => {
            const sectorDataItem = dataInput[sector];
            if (!sectorDataItem || !sectorDataItem.years) return;
            sectorDataItem.years.forEach(year => years.add(year));
        });

        const sortedYears = Array.from(years).sort((a, b) => a - b);
        aggregated.years = sortedYears;

        Object.keys(dataInput).forEach(sector => {
            const select = document.querySelector(`.sector-model-select[data-sector="${sector}"]`);
            const modelsForThisSector = sourceModels[sector] || ['WAM'];
            const selectedModel = select ? select.value : (modelsForThisSector.includes('User Data') ? 'User Data' : modelsForThisSector[0]);
            
            const sectorDataItem = dataInput[sector];
            if (!sectorDataItem || !sectorDataItem[selectedModel]) return;

            aggregated[sector] = {}; // Store model data under sector
            aggregated[sector][selectedModel] = sortedYears.map(year => {
                const index = sectorDataItem.years.indexOf(year);
                return index !== -1 && sectorDataItem[selectedModel][index] !== undefined ? (sectorDataItem[selectedModel][index] || 0) : 0;
            });
        });
        
        // For consolidated chart, we need a flat structure of sector -> values array
        // The current logic in updateScenarioComparison already reconstructs this for datasets.
        // This aggregateSectorData function is more for creating a consistent data structure
        // if we were to, for example, pass it to a single chart rendering function that expects this.
        // Let's adjust it to fit the current usage for consolidated comparison plotting.
        // The main goal is to get `aggregated.years` and `aggregated[sectorName][modelName]` access.
        // The current implementation seems to align with this for the plot functions.

        const availableModels = new Set();
        Object.keys(dataInput).forEach(sector => {
            if (dataInput[sector] && dataInput[sector].models) {
                dataInput[sector].models.forEach(model => availableModels.add(model));
            }
        });
        aggregated.models = Array.from(availableModels); // This is a bit generic, might need refinement

        return aggregated;
    }

    function showNotification(type, message, duration = 5000) {
        try {
            let notificationContainer = document.getElementById('notificationContainer');
            if (!notificationContainer) {
                notificationContainer = document.createElement('div');
                notificationContainer.id = 'notificationContainer';
                notificationContainer.className = 'notification-container';
                document.body.appendChild(notificationContainer);
            }

            const notification = document.createElement('div');
            notification.className = `alert alert-${type} alert-dismissible fade show shadow-sm`; // Added shadow
            notification.innerHTML = `
            <i class="fas ${type === 'success' ? 'fa-check-circle' : type === 'danger' ? 'fa-exclamation-triangle' : 'fa-info-circle'} me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
            notificationContainer.appendChild(notification);

            if (duration > 0) {
                setTimeout(() => {
                    try {
                        const bsAlert = bootstrap.Alert.getInstance(notification);
                        if (bsAlert) {
                            bsAlert.close();
                        } else if (notification.parentNode) {
                           // Fallback removal if Bootstrap instance not found
                           notification.classList.remove('show');
                           setTimeout(() => { if (notification.parentNode) notification.remove(); }, 150); // Wait for fade
                        }
                    } catch (error) {
                        console.error('Error removing notification:', error);
                        if (notification.parentNode) notification.remove(); // Force remove
                    }
                }, duration);
            }
        } catch (error) {
            console.error('Error showing notification:', error);
            console.log(`${type.toUpperCase()}: ${message}`); // Fallback to console
            alert(`${type.toUpperCase()}: ${message}`); // Fallback to alert
        }
    }


    document.getElementById('saveConsolidated').addEventListener('click', () => {
        saveConsolidatedData(currentScenario);
    });

    function saveConsolidatedData(scenario) {
        try {
            showNotification('info', 'Preparing consolidated data for saving...', 3000);
        } catch (error) {
            console.log('Info: Preparing consolidated data for saving...');
        }

        const params = new URLSearchParams({
            unit: 'kWh', 
            from_year: yearRange.from,
            to_year: yearRange.to
        });

        document.querySelectorAll('.sector-model-select').forEach(select => {
            params.append(`model_${select.dataset.sector}`, select.value);
        });

        fetch(`/demand/api/save_consolidated_data/${scenario}?${params.toString()}`)
            .then(response => {
                if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
                return response.json();
            })
            .then(data => {
                if (data.status === 'success') {
                    showNotification('success', `Consolidated data saved successfully to ${data.file_path}`, 7000);
                } else {
                    showNotification('danger', data.message || 'Failed to save data', 7000);
                }
            })
            .catch(error => {
                console.error('Error saving consolidated data:', error);
                showNotification('danger', `Failed to save data: ${error.message}`, 7000);
            });
    }
});
