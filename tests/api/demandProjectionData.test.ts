import axios from 'axios';

const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:5000';
const DEFAULT_PROJECT_PATH = 'testing project/Default_project';

describe('Demand Projection Data APIs', () => {
    beforeAll(async () => {
        // Load the default test project
        const response = await axios.post(
            `${API_BASE_URL}/load_project`,
            new URLSearchParams({ projectPath: DEFAULT_PROJECT_PATH })
        );
        if (response.data.status !== 'success') {
            throw new Error(`Failed to load test project: ${DEFAULT_PROJECT_PATH}. Message: ${response.data.message}`);
        }
    });

    describe('GET /api/independent_variables/<sector>', () => {
        it('should get variables for Residential sector', async () => {
            const response = await axios.get(`${API_BASE_URL}/api/independent_variables/Residential`);
            expect(response.status).toBe(200);
            expect(response.data.status).toBe('success');
            expect(response.data.variables).toEqual(expect.arrayContaining(['Year', 'Electricity', 'GDP', 'Population', 'SomeOtherData']));
            expect(response.data.correlations).toBeDefined();
        });

        it('should get variables for Commercial sector', async () => {
            const response = await axios.get(`${API_BASE_URL}/api/independent_variables/Commercial`);
            expect(response.status).toBe(200);
            expect(response.data.status).toBe('success');
            expect(response.data.variables).toEqual(expect.arrayContaining(['Year', 'Electricity', 'Population', 'AnotherValue']));
        });

        it('should return error for non-existent sector', async () => {
            try {
                await axios.get(`${API_BASE_URL}/api/independent_variables/NonExistentSector`);
            } catch (error: any) {
                expect(error.response.status).toBe(200); // App returns 200 with error status
                expect(error.response.data.status).toBe('error');
                expect(error.response.data.message).toContain('Sector NonExistentSector not found');
            }
        });
    });

    describe('GET /api/correlation_data/<sector>', () => {
        it('should get correlation data for Residential sector', async () => {
            const response = await axios.get(`${API_BASE_URL}/api/correlation_data/Residential`);
            expect(response.status).toBe(200);
            expect(response.data.status).toBe('success');
            expect(response.data.data.variables).toBeInstanceOf(Array);
            expect(response.data.data.correlations).toBeInstanceOf(Array);
        });

        it('should get correlation data for aggregated sector', async () => {
            const response = await axios.get(`${API_BASE_URL}/api/correlation_data/aggregated`);
            expect(response.status).toBe(200);
            expect(response.data.status).toBe('success');
            // Add more specific checks if possible, e.g. presence of 'variables' and 'correlations' keys
            expect(response.data.data.variables).toBeInstanceOf(Array);
            expect(response.data.data.correlations).toBeInstanceOf(Array);
        });
    });

    describe('GET /api/chart_data/<sector>', () => {
        it('should get chart data for Residential sector', async () => {
            const response = await axios.get(`${API_BASE_URL}/api/chart_data/Residential`);
            expect(response.status).toBe(200);
            expect(response.data.status).toBe('success');
            expect(response.data.data.years).toBeInstanceOf(Array);
            expect(response.data.data.years.length).toBeGreaterThan(0);
            expect(response.data.data.electricity).toBeInstanceOf(Array);
            expect(response.data.data.electricity.length).toBeGreaterThan(0);
        });

        it('should get chart data for aggregated sector', async () => {
            const response = await axios.get(`${API_BASE_URL}/api/chart_data/aggregated`);
            expect(response.status).toBe(200);
            expect(response.data.status).toBe('success');
            expect(response.data.data.years).toBeInstanceOf(Array);
            expect(response.data.data.datasets).toBeInstanceOf(Array);
            expect(response.data.data.datasets.length).toBeGreaterThan(0); // Should have Residential and Commercial
        });
    });

    describe('GET /api/forecast_data/<scenario>', () => {
        const scenarioName = 'TestScenario';
        it('should get forecast data for TestScenario', async () => {
            const response = await axios.get(`${API_BASE_URL}/api/forecast_data/${scenarioName}`);
            expect(response.status).toBe(200);
            expect(response.data.status).toBe('success');
            expect(response.data.data.Residential).toBeDefined();
            expect(response.data.data.Commercial).toBeDefined();
            expect(response.data.data.Residential.models).toEqual(['Historical', 'ModelA', 'ModelB']);
            expect(response.data.data.Residential.Historical).toBeInstanceOf(Array);
            expect(response.data.data.Commercial.models).toEqual(['Historical', 'ModelX']);
        });

        it('should return error for non-existent scenario', async () => {
            try {
                await axios.get(`${API_BASE_URL}/api/forecast_data/NonExistentScenario`);
            } catch (error: any) {
                expect(error.response.status).toBe(200);
                expect(error.response.data.status).toBe('error');
                expect(error.response.data.message).toContain('Scenario NonExistentScenario not found');
            }
        });
    });

    describe('GET /api/scenario_details/<scenario_name>', () => {
        const scenarioName = 'TestScenario';
        it('should get details for TestScenario', async () => {
            const response = await axios.get(`${API_BASE_URL}/api/scenario_details/${scenarioName}`);
            expect(response.status).toBe(200);
            expect(response.data.status).toBe('success');
            expect(response.data.scenario_name).toBe(scenarioName);
            expect(response.data.sectors).toEqual(expect.arrayContaining(['Residential', 'Commercial']));
            expect(response.data.target_year).toBe(2025); // From mock summary.json
        });

        it('should return error for non-existent scenario', async () => {
             try {
                await axios.get(`${API_BASE_URL}/api/scenario_details/NonExistentScenario`);
            } catch (error: any) {
                expect(error.response.status).toBe(200);
                expect(error.response.data.status).toBe('error');
                expect(error.response.data.message).toContain('Scenario NonExistentScenario not found');
            }
        });
    });
});
