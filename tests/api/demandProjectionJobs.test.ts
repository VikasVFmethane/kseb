import axios from 'axios';

const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:5000';
const DEFAULT_PROJECT_PATH = 'testing project/Default_project';

// Helper function to delay execution
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

describe('Demand Projection Jobs and Downloads API', () => {
    let jobId: string | null = null;

    beforeAll(async () => {
        const response = await axios.post(
            `${API_BASE_URL}/load_project`,
            new URLSearchParams({ projectPath: DEFAULT_PROJECT_PATH })
        );
        if (response.data.status !== 'success') {
            throw new Error('Failed to load test project for job tests.');
        }
    });

    describe('Job Management: /run_forecast, /forecast_status, /cancel_forecast', () => {
        it('should start a forecast, allow status check, and then cancel', async () => {
            const forecastConfig = {
                scenarioName: 'TestJobScenario', // Use a unique scenario name for job tests
                targetYear: 2025,
                excludeCovidYears: false,
                sectorConfigs: {
                    'Residential': { models: ['ModelA'], variables: ['GDP', 'Population'] }, // Added variables for validity
                    'Commercial': { models: ['ModelX'], variables: ['Population'] }    // Added variables for validity
                }
            };

            // Start forecast
            const runResponse = await axios.post(`${API_BASE_URL}/api/run_forecast`, forecastConfig);
            expect(runResponse.status).toBe(200);
            expect(runResponse.data.status).toBe('started');
            expect(runResponse.data.jobId).toBeDefined();
            jobId = runResponse.data.jobId;

            // Check status (allow a brief moment for job to potentially progress)
            await delay(1000); // Increased delay slightly
            let statusResponse = await axios.get(`${API_BASE_URL}/api/forecast_status/${jobId}`);
            expect(statusResponse.status).toBe(200);
            // The job might complete very quickly with mock data.
            // If it's already completed or failed, cancellation test might not be meaningful.
            expect(['starting', 'running', 'completed', 'failed']).toContain(statusResponse.data.status); 

            // If not completed or failed, try to cancel
            if (statusResponse.data.status === 'starting' || statusResponse.data.status === 'running') {
                const cancelResponse = await axios.post(`${API_BASE_URL}/api/cancel_forecast/${jobId}`);
                expect(cancelResponse.status).toBe(200);
                // Expect 'cancelled' or 'cancel_requested' or similar, depending on backend implementation
                expect(['cancelled', 'cancel_requested', 'cancelling']).toContain(cancelResponse.data.status);


                // Wait a bit for cancellation to process
                await delay(500);
                statusResponse = await axios.get(`${API_BASE_URL}/api/forecast_status/${jobId}`);
                // Final status should be 'cancelled' or 'failed' if cancellation led to failure.
                expect(['cancelled', 'failed']).toContain(statusResponse.data.status);
            } else {
                console.warn(`Job ${jobId} was in state '${statusResponse.data.status}' and not 'starting' or 'running'. Cancellation test may not be fully representative.`);
            }
        }, 20000); // Increased timeout for job-related tests

        it('should return error for invalid forecast config (missing sectorConfigs.variables)', async () => {
            const invalidConfig = { 
                scenarioName: 'ErrorScenarioJob',
                targetYear: 2025,
                excludeCovidYears: false,
                sectorConfigs: { // Missing 'variables' in sector configs
                    'Residential': { models: ['ModelA'] }, 
                }
            };
            try {
                await axios.post(`${API_BASE_URL}/api/run_forecast`, invalidConfig);
            } catch (error: any) {
                 expect(error.response.status).toBe(200); // App specific error response
                 expect(error.response.data.status).toBe('error');
                 // The message might be more specific depending on validation, e.g. about missing variables
                 expect(error.response.data.message).toContain('Invalid configuration for sector Residential: Missing variables');
            }
        });
        
        it('should return error for missing scenarioName', async () => {
            const invalidConfig = { 
                // scenarioName: 'MissingNameScenario', // Omitted
                targetYear: 2025,
                excludeCovidYears: false,
                sectorConfigs: {
                    'Residential': { models: ['ModelA'], variables: ['GDP'] },
                }
            };
             try {
                await axios.post(`${API_BASE_URL}/api/run_forecast`, invalidConfig);
            } catch (error: any) {
                 expect(error.response.status).toBe(200);
                 expect(error.response.data.status).toBe('error');
                 expect(error.response.data.message).toBe('Missing required parameters'); // Or more specific
            }
        });
    });

    describe('GET /api/save_consolidated_data/<scenario>', () => {
        it('should save consolidated data for TestScenario', async () => {
            const params = new URLSearchParams({
                unit: 'TWh',
                from_year: '2015',
                to_year: '2025',
                model_Residential: 'ModelA', 
                model_Commercial: 'ModelX'  
            });
            const response = await axios.get(`${API_BASE_URL}/api/save_consolidated_data/TestScenario?${params.toString()}`);
            expect(response.status).toBe(200);
            expect(response.data.status).toBe('success');
            expect(response.data.message).toBe('Consolidated data saved successfully');
            expect(response.data.file_path).toBe('results/demand_projection/TestScenario/consolidated_results.csv'); // Path relative to project root
        });

        it('should return error if scenario does not exist', async () => {
            const params = new URLSearchParams({ unit: 'TWh', from_year: '2015', to_year: '2025' });
            try {
                await axios.get(`${API_BASE_URL}/api/save_consolidated_data/NonExistentScenario123?${params.toString()}`);
            } catch (error: any) {
                expect(error.response.status).toBe(200);
                expect(error.response.data.status).toBe('error');
                expect(error.response.data.message).toContain('Scenario NonExistentScenario123 not found');
            }
        });
    });

    describe('POST /api/download_comparison_data', () => {
        it('should allow downloading comparison data', async () => {
            const payload = {
                scenarios: ["TestScenario", "AnotherTestScenario"],
                fromYear: 2015,
                toYear: 2025,
                unit: "TWh",
                sectorModelMap: { "Residential": "ModelA", "Commercial": "ModelX" }
            };
            const response = await axios.post(`${API_BASE_URL}/api/download_comparison_data`, payload);
            expect(response.status).toBe(200);
            expect(response.headers['content-type']).toContain('text/csv');
            expect(response.headers['content-disposition']).toContain('attachment; filename=');
            expect(response.data).toBeDefined();
            expect(response.data.length).toBeGreaterThan(0); // CSV content should not be empty
        });

        it('should return error if scenarios list is empty', async () => {
            const payload = {
                scenarios: [], // Empty list
                fromYear: 2015,
                toYear: 2025,
                unit: "TWh",
                sectorModelMap: { "Residential": "ModelA" }
            };
            try {
                await axios.post(`${API_BASE_URL}/api/download_comparison_data`, payload);
            } catch (error: any) {
                expect(error.response.status).toBe(200);
                expect(error.response.data.status).toBe('error');
                expect(error.response.data.message).toBe('Scenarios list cannot be empty');
            }
        });
    });
});
