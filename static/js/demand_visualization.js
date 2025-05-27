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

        fetch(`demand/api/download_csv/${scenario}/${sector}?${params.toString()}`)
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
            chart2.style.display = 'block';
        } else {
            container.classList.remove('split');
            chart2.style.display = 'none';
        }
    }

    async function loadForecastData(scenario) {
        try {
            const response = await fetch('/demand/api/forecast_data/${scenario}', {
                headers: { 'Accept': 'application/json' }
            });
            if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
            const result = await response.json();
            if (result.status !== 'success') throw new Error(result.message || 'Failed to load forecast data');
            sectorData = result.data;

            // Initialize sectorModels and update sidebar dropdowns
            sectorModels = {};
            Object.keys(sectorData).forEach(sector => {
                sectorModels[sector] = sectorData[sector].models || ['WAM'];
                updateModelDropdown(sector);
            });

            updateYearDropdowns();
            comparisonScenarios = { consolidated: '' };
            document.querySelectorAll('[id^="compareScenario"]').forEach(select => {
                const sector = select.dataset.sector;
                select.value = '';
                comparisonScenarios[sector] = '';
                updateComparisonContainerWidth(sector);
            });
            updateAllViews();
        } catch (error) {
            console.error('Error loading forecast data:', error);
            showNotification('danger', `Failed to load forecast data: ${error.message}`);
        }
    }

    // New function to load comparison data
    async function loadComparisonData(scenario, sector) {
        try {
            const response = await fetch('/demand/api/forecast_data/${scenario}', {
                headers: { 'Accept': 'application/json' }
            });
            if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
            const result = await response.json();
            if (result.status !== 'success') throw new Error(result.message || 'Failed to load comparison data');

            // Store comparison data
            comparisonData[scenario] = result.data;

            // Update comparison view
            updateComparisonContainerWidth(sector);
            updateScenarioComparison(sector, scenario);
        } catch (error) {
            console.error('Error loading comparison data:', error);
            showNotification('danger', `Failed to load comparison data: ${error.message}`);
        }
    }

    function updateModelDropdown(sector) {
        const select = document.querySelector(`.sector-model-select[data-sector="${sector}"]`);
        if (!select) return;
        const models = sectorModels[sector] || ['WAM'];
        select.innerHTML = models.map(model => `<option value="${model}">${model}</option>`).join('');
        // Set default to User Data if available, else WAM, else first model
        select.value = models.includes('User Data') ? 'User Data' : models.includes('WAM') ? 'WAM' : models[0];
    }

    function updateYearDropdowns() {
        const fromYearSelect = document.getElementById('fromYear');
        const toYearSelect = document.getElementById('toYear');
        let allYears = new Set();
        Object.values(sectorData).forEach(data => {
            if (data && data.years) {
                data.years.forEach(year => allYears.add(year));
            }
        });
        allYears = Array.from(allYears).sort((a, b) => a - b);
        if (allYears.length === 0) {
            console.warn('No valid years found in API data');
            return;
        }
        fromYearSelect.innerHTML = '';
        toYearSelect.innerHTML = '';
        allYears.forEach(year => {
            const optionFrom = document.createElement('option');
            optionFrom.value = year;
            optionFrom.textContent = year;
            if (year === yearRange.from) optionFrom.selected = true;
            fromYearSelect.appendChild(optionFrom);
            const optionTo = document.createElement('option');
            optionTo.value = year;
            optionTo.textContent = year;
            if (year === yearRange.to) optionTo.selected = true;
            toYearSelect.appendChild(optionTo);
        });
        yearRange.from = parseInt(fromYearSelect.value);
        yearRange.to = parseInt(toYearSelect.value);
    }

    function switchSector(sector) {
        currentSector = sector;
        document.querySelectorAll('.sector-button').forEach(btn => btn.classList.remove('active'));
        document.querySelector(`.sector-button[data-sector="${sector}"]`).classList.add('active');
        document.querySelectorAll('.sector-section').forEach(section => section.classList.remove('active'));
        document.getElementById(`${sector}-section`).classList.add('active');
        updateAllViews();
    }

    function switchView(sector, view) {
        document.querySelectorAll(`.view-toggle-button[data-sector="${sector}"]`).forEach(btn => btn.classList.remove('active'));
        document.querySelector(`.view-toggle-button[data-sector="${sector}"][data-view="${view}"]`).classList.add('active');
        document.querySelectorAll(`#${sector}-section .view-content`).forEach(content => content.style.display = 'none');
        document.getElementById(`${sector}-${view}-view`).style.display = 'flex';
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
        if (!sectorData[sector] && sector !== 'consolidated') {
            showNotification('warning', `No data available for ${sector}`);
            return;
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
        tableBody.innerHTML = '';
        const years = new Set();
        const dataByYear = {};

        Object.keys(sectorData).forEach(sector => {
            const select = document.querySelector(`.sector-model-select[data-sector="${sector}"]`);
            const model = select ? select.value : (sectorModels[sector].includes('User Data') ? 'User Data' : 'WAM');
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
            row.innerHTML += `<td class="numeric">${total.toFixed(2)}</td>`;
            tableBody.appendChild(row);
        });

        document.querySelector('#consolidated-table-view .table-loading').style.display = 'none';
    }

    function updateConsolidatedChart() {
        const canvas = document.getElementById('consolidatedChart');
        const chartType = document.querySelector('.chart-type-controls .btn.active')?.dataset.chartType || 'area';
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
            const model = select ? select.value : (sectorModels[sector].includes('User Data') ? 'User Data' : 'WAM');
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

        document.querySelector('#consolidated-chart-view .chart-loading').style.display = 'none';
    }

    function updateSectorTable(sector) {
        const tableBody = document.querySelector(`#${sector}Table tbody`);
        tableBody.innerHTML = '';
        const data = sectorData[sector];
        if (!data || !data.years) {
            showNotification('warning', `No data available for ${sector}`);
            return;
        }
        // Use available models for this sector
        const models = sectorModels[sector] || ['WAM'];
        // Update table headers dynamically
        const tableHead = document.querySelector(`#${sector}Table thead tr`);
        tableHead.innerHTML = `<th>Year</th>` + models.map(model => `<th>${model}</th>`).join('');
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
        document.querySelector(`#${sector}-table-view .table-loading`).style.display = 'none';
    }

    function updateSectorChart(sector) {
        const canvas = document.getElementById(`${sector}Chart`);
        const data = sectorData[sector];
        if (!data || !data.years) {
            showNotification('warning', `No data available for ${sector}`);
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

        document.querySelector(`#${sector}-chart-view .chart-loading`).style.display = 'none';
    }

    async function updateScenarioComparison(sector, compareScenario) {
        const isConsolidated = sector === 'consolidated';
        const canvas1 = document.getElementById(`${sector}ComparisonChart1`);
        const canvas2 = document.getElementById(`${sector}ComparisonChart2`);

        // For the primary scenario (current scenario)
        let data1 = isConsolidated ? aggregateSectorData(sectorData) : sectorData[sector];
        let data2 = null;

        if (!data1 || !data1.years) {
            showNotification('warning', `No data available for ${sector}`);
            return;
        }

        // For the comparison scenario
        if (compareScenario) {
            try {
                if (comparisonData[compareScenario]) {
                    // Use already loaded data
                    data2 = isConsolidated ?
                        aggregateSectorData(comparisonData[compareScenario], true) :
                        comparisonData[compareScenario][sector];

                    if (!data2 || !data2.years) {
                        throw new Error('No data available for comparison scenario');
                    }

                    // Update models for comparison scenario
                    if (data2.models) {
                        sectorModels[`${sector}_compare`] = data2.models;
                    }
                } else {
                    // Load data from server
                    const response = await fetch('/demand/api/forecast_data/${compareScenario}', {
                        headers: { 'Accept': 'application/json' }
                    });
                    if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
                    const result = await response.json();
                    if (result.status !== 'success') throw new Error('Scenario data not available');

                    // Store for future use
                    comparisonData[compareScenario] = result.data;

                    data2 = isConsolidated ?
                        aggregateSectorData(result.data, true) :
                        result.data[sector];

                    if (!data2 || !data2.years) throw new Error('No data available for comparison scenario');

                    // Update models for comparison scenario
                    if (data2.models) {
                        sectorModels[`${sector}_compare`] = data2.models;
                    }
                }
            } catch (error) {
                console.error('Error loading comparison scenario:', error);
                showNotification('danger', `Failed to load comparison scenario: ${error.message}`);
                data2 = null;
            }
        }

        // Render first chart (primary scenario)
        const years1 = data1.years.filter(year => year >= yearRange.from && year <= yearRange.to);

        let datasets1 = [];

        if (isConsolidated) {
            // For consolidated view, we show all sectors with their selected models
            Object.keys(sectorData).forEach((sectorName, i) => {
                const select = document.querySelector(`.sector-model-select[data-sector="${sectorName}"]`);
                const selectedModel = select ? select.value :
                    (sectorModels[sectorName] && sectorModels[sectorName].includes('User Data') ?
                        'User Data' : 'WAM');

                if (data1[sectorName]) {
                    datasets1.push({
                        label: sectorName,
                        data: years1.map(year => {
                            const yearIndex = data1.years.indexOf(year);
                            return yearIndex !== -1 ?
                                (data1[sectorName][yearIndex] || 0) / unitFactors[currentUnit] : 0;
                        }),
                        backgroundColor: `rgba(${(i * 50) % 255}, ${(i * 100) % 255}, ${(i * 150) % 255}, 0.7)`,
                        borderColor: `rgba(${(i * 50) % 255}, ${(i * 100) % 255}, ${(i * 150) % 255}, 1)`,
                        fill: false,
                        tension: 0.1
                    });
                }
            });
        } else {
            // For individual sector view, show all models for that sector
            const select = document.querySelector(`.sector-model-select[data-sector="${sector}"]`);
            const selectedModel = select ? select.value :
                (sectorModels[sector] && sectorModels[sector].includes('User Data') ?
                    'User Data' : 'WAM');

            const models = sectorModels[sector] || ['WAM'];

            datasets1 = models.map(model => ({
                label: model,
                data: data1.years.map((year, i) => {
                    if (year >= yearRange.from && year <= yearRange.to) {
                        return (data1[model] && data1[model][i] !== undefined ?
                            data1[model][i] : 0) / unitFactors[currentUnit];
                    }
                    return null;
                }).filter(v => v !== null),
                backgroundColor: modelColors[model] || 'rgba(128, 128, 128, 0.7)',
                borderColor: (modelColors[model] || 'rgba(128, 128, 128, 0.7)').replace('0.7', '1'),
                fill: false,
                tension: 0.1
            }));
        }

        if (charts[`${sector}ComparisonChart1`]) charts[`${sector}ComparisonChart1`].destroy();
        charts[`${sector}ComparisonChart1`] = new Chart(canvas1, {
            type: 'line',
            data: { labels: years1, datasets: datasets1 },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true, title: { display: true, text: currentUnit }, ticks: { callback: value => Number.isFinite(value) ? value.toFixed(2) : value } },
                    x: { title: { display: true, text: 'Year' } }
                },
                plugins: {
                    title: { display: true, text: currentScenario, font: { size: 14 } },
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

        // Render second chart if comparison data exists
        if (data2) {
            const years2 = data2.years.filter(year => year >= yearRange.from && year <= yearRange.to);

            let datasets2 = [];

            if (isConsolidated) {
                // Same handling for consolidated view in the comparison chart
                Object.keys(comparisonData[compareScenario]).forEach((sectorName, i) => {
                    const select = document.querySelector(`.sector-model-select[data-sector="${sectorName}"]`);
                    const selectedModel = select ? select.value :
                        (sectorModels[sectorName] && sectorModels[sectorName].includes('User Data') ?
                            'User Data' : 'WAM');

                    if (data2[sectorName]) {
                        datasets2.push({
                            label: sectorName,
                            data: years2.map(year => {
                                const yearIndex = data2.years.indexOf(year);
                                return yearIndex !== -1 ?
                                    (data2[sectorName][yearIndex] || 0) / unitFactors[currentUnit] : 0;
                            }),
                            backgroundColor: `rgba(${(i * 50) % 255}, ${(i * 100) % 255}, ${(i * 150) % 255}, 0.5)`,
                            borderColor: `rgba(${(i * 50) % 255}, ${(i * 100) % 255}, ${(i * 150) % 255}, 0.8)`,
                            fill: false,
                            tension: 0.1
                        });
                    }
                });
            } else {
                // For individual sector, show all models with the selected one highlighted
                const models2 = sectorModels[`${sector}_compare`] || sectorModels[sector] || ['WAM'];
                const select = document.querySelector(`.sector-model-select[data-sector="${sector}"]`);
                const selectedModel = select ? select.value :
                    (models2.includes('User Data') ? 'User Data' : 'WAM');

                datasets2 = models2.map(model => ({
                    label: model,
                    data: data2.years.map((year, i) => {
                        if (year >= yearRange.from && year <= yearRange.to) {
                            return (data2[model] && data2[model][i] !== undefined ?
                                data2[model][i] : 0) / unitFactors[currentUnit];
                        }
                        return null;
                    }).filter(v => v !== null),
                    backgroundColor: (modelColors[model] || 'rgba(128, 128, 128, 0.5)').replace('0.7', '0.5'),
                    borderColor: (modelColors[model] || 'rgba(128, 128, 128, 0.8)').replace('0.7', '0.8'),
                    fill: false,
                    tension: 0.1
                }));
            }

            if (charts[`${sector}ComparisonChart2`]) charts[`${sector}ComparisonChart2`].destroy();
            charts[`${sector}ComparisonChart2`] = new Chart(canvas2, {
                type: 'line',
                data: { labels: years2, datasets: datasets2 },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true, title: { display: true, text: currentUnit }, ticks: { callback: value => Number.isFinite(value) ? value.toFixed(2) : value } },
                        x: { title: { display: true, text: 'Year' } }
                    },
                    plugins: {
                        title: { display: true, text: compareScenario, font: { size: 14 } },
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
        } else {
            if (charts[`${sector}ComparisonChart2`]) charts[`${sector}ComparisonChart2`].destroy();
            const ctx = canvas2.getContext('2d');
            ctx.clearRect(0, 0, canvas2.width, canvas2.height);
        }

        document.querySelector(`#${sector}-comparison-view .chart-loading`).style.display = 'none';
    }

    function aggregateSectorData(data, isComparison = false) {
        const years = new Set();
        const aggregated = {};

        // Collect all available years
        Object.keys(data).forEach(sector => {
            const sectorData = data[sector];
            if (!sectorData || !sectorData.years) return;
            sectorData.years.forEach(year => years.add(year));
        });

        const sortedYears = Array.from(years).sort((a, b) => a - b);

        // Process each sector with the selected model
        Object.keys(data).forEach(sector => {
            // Get the selected model for this sector
            const select = document.querySelector(`.sector-model-select[data-sector="${sector}"]`);
            const selectedModel = select ? select.value :
                (data[sector] && data[sector].models && data[sector].models.includes('User Data') ?
                    'User Data' : 'WAM');

            const sectorData = data[sector];
            if (!sectorData || !sectorData[selectedModel]) return;

            // Create an array of values for this sector based on the selected model
            // Fill with actual data where available, and zeros where not
            aggregated[sector] = sortedYears.map(year => {
                const index = sectorData.years.indexOf(year);
                return index !== -1 ? (sectorData[selectedModel][index] || 0) : 0;
            });
        });

        // Add the years array to the result
        aggregated.years = sortedYears;

        // Add available models (keeping this generic)
        const availableModels = new Set();
        Object.keys(data).forEach(sector => {
            if (data[sector] && data[sector].models) {
                data[sector].models.forEach(model => availableModels.add(model));
            }
        });
        aggregated.models = Array.from(availableModels);

        return aggregated;
    }

    function showNotification(type, message) {
        try {
            // Check if notification container exists, create if it doesn't
            let notificationContainer = document.getElementById('notificationContainer');
            if (!notificationContainer) {
                notificationContainer = document.createElement('div');
                notificationContainer.id = 'notificationContainer';
                notificationContainer.className = 'notification-container';
                notificationContainer.style.position = 'fixed';
                notificationContainer.style.top = '80px';
                notificationContainer.style.right = '20px';
                notificationContainer.style.zIndex = '1060';
                notificationContainer.style.maxWidth = '400px';
                document.body.appendChild(notificationContainer);
            }

            // Create notification element
            const notification = document.createElement('div');
            notification.className = `alert alert-${type} alert-dismissible fade show`;
            notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;

            // Add to container
            notificationContainer.appendChild(notification);

            // Auto-dismiss after 5 seconds
            setTimeout(() => {
                try {
                    if (notification.parentNode) {
                        notification.remove();
                    }
                } catch (error) {
                    console.error('Error removing notification:', error);
                }
            }, 5000);
        } catch (error) {
            // Fallback if DOM manipulation fails
            console.error('Error showing notification:', error);
            console.log(`${type.toUpperCase()}: ${message}`);
        }
    }


    // Add event listener for the "Save" button
    document.getElementById('saveConsolidated').addEventListener('click', () => {
        saveConsolidatedData(currentScenario);
    });

    /**
     * Save consolidated data to the server
     * 
     * @param {string} scenario - The current scenario name
     */
    function saveConsolidatedData(scenario) {
        // Show a loading notification
        try {
            showNotification('info', 'Preparing consolidated data for saving...');
        } catch (error) {
            console.log('Info: Preparing consolidated data for saving...');
        }

        // Create data object to send to server
        const params = new URLSearchParams({
            unit: 'kWh', // Always save in kWh format
            from_year: yearRange.from,
            to_year: yearRange.to
        });

        // Add model selection for each sector
        document.querySelectorAll('.sector-model-select').forEach(select => {
            params.append(`model_${select.dataset.sector}`, select.value);
        });

        // Make API request to save
        fetch(`demand/api/save_consolidated_data/${scenario}?${params.toString()}`)
            .then(response => {
                if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
                return response.json();
            })
            .then(data => {
                if (data.status === 'success') {
                    try {
                        showNotification('success', `Consolidated data saved successfully to ${data.file_path}`);
                    } catch (error) {
                        console.log(`Success: Data saved successfully to ${data.file_path}`);
                        alert(`Success: Data saved successfully to ${data.file_path}`);
                    }
                } else {
                    try {
                        showNotification('danger', data.message || 'Failed to save data');
                    } catch (error) {
                        console.error(`Error: ${data.message || 'Failed to save data'}`);
                        alert(`Error: ${data.message || 'Failed to save data'}`);
                    }
                }
            })
            .catch(error => {
                console.error('Error saving consolidated data:', error);
                try {
                    showNotification('danger', `Failed to save data: ${error.message}`);
                } catch (notifyError) {
                    console.error(`Failed to save data: ${error.message}`);
                    alert(`Failed to save data: ${error.message}`);
                }
            });
    }
});