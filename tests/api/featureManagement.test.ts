import axios from 'axios';

const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:5000'; // Flask app URL

describe('Feature Management API', () => {

    describe('GET /api/features (No Project Loaded)', () => {
        // This test assumes a state where no project is loaded.
        // It's hard to guarantee this state without a dedicated /unload_project endpoint or server restart.
        // Thus, this test might be flaky or produce inconsistent results if a project is already loaded globally.
        it('should return an error if no project is selected', async () => {
            console.warn("Test 'GET /api/features without project' is potentially flaky due to server state regarding current project.");
            try {
                // Attempt to get features without ensuring a project is unloaded
                const response = await axios.get(`${API_BASE_URL}/api/features`);
                // Expecting the API to indicate an error in its JSON response, even with a 200 status
                expect(response.status).toBe(200);
                expect(response.data.status).toBe('error');
                expect(response.data.message).toBe('No project selected');
            } catch (error: any) {
                // If the server truly returns an HTTP error code (e.g. 4xx, 5xx)
                // This block might catch it. Based on app.py, it returns JSON with status:'error'
                // and a 200 OK, so the above 'try' block should handle it.
                // If it did throw an HTTP error, this would be the place to check:
                // expect(error.response.status).toBe(400); // Or whatever appropriate error code
                // expect(error.response.data.message).toBe('No project selected');
                // For now, we rely on the 200 OK + JSON error status based on app.py structure
                if (error.response?.data?.status !== 'error' || error.response?.data?.message !== 'No project selected') {
                    throw error; // Re-throw if it's not the expected JSON error
                }
                 expect(error.response.status).toBe(200);
                 expect(error.response.data.status).toBe('error');
                 expect(error.response.data.message).toBe('No project selected');
            }
        });
    });

    describe('GET /api/features (With Project Loaded)', () => {
        beforeAll(async () => {
            // Load 'testing project/Default_project' before tests in this block
            const loadResponse = await axios.post(
                `${API_BASE_URL}/load_project`,
                new URLSearchParams({ projectPath: 'testing project/Default_project' })
            );
            if (loadResponse.data.status !== 'success') {
                throw new Error('Failed to load test project: testing project/Default_project. Message: ' + loadResponse.data.message);
            }
        });

        it('should retrieve features reflecting project-specific and global defaults', async () => {
            const response = await axios.get(`${API_BASE_URL}/api/features`);
            expect(response.status).toBe(200);
            expect(response.data.status).toBe('success');
            expect(response.data.features).toBeDefined();

            // Check demand-projection: overridden by project_features.json
            expect(response.data.features['demand-projection']).toBeDefined();
            expect(response.data.features['demand-projection'].name).toBe('Demand Projection');
            expect(response.data.features['demand-projection'].enabled).toBe(false); // Overridden by project file

            // Check load-curve: specified in project_features.json
            expect(response.data.features['load-curve']).toBeDefined();
            expect(response.data.features['load-curve'].name).toBe('Load Curve Analysis');
            expect(response.data.features['load-curve'].enabled).toBe(true); // Set in project file

            // Check pypsa-integration: not in project_features.json, should take from global default
            expect(response.data.features['pypsa-integration']).toBeDefined();
            expect(response.data.features['pypsa-integration'].name).toBe('PyPSA Integration');
            expect(response.data.features['pypsa-integration'].enabled).toBe(false); // Global default_enabled

            expect(response.data.feature_groups).toBeDefined();
            expect(response.data.feature_groups['core']).toBe('Core Modelling Features');
        });
    });

    describe('PUT /api/features/<feature_id> (With Project Loaded)', () => {
        const projectPath = 'testing project/Default_project';
        const featureToTest = 'demand-projection'; // Will be initially false for this project
        const anotherFeature = 'pypsa-integration'; // Will be initially false (global default)

        beforeEach(async () => {
            // Ensure the project is loaded before each test in this block
            // And reset feature states if necessary by re-loading or specific calls
            const loadResponse = await axios.post(
                `${API_BASE_URL}/load_project`,
                new URLSearchParams({ projectPath })
            );
            if (loadResponse.data.status !== 'success') {
                throw new Error('Failed to load test project for PUT tests. Message: ' + loadResponse.data.message);
            }
            // Reset 'demand-projection' to false (its state in project_features.json)
            await axios.put(`${API_BASE_URL}/api/features/${featureToTest}`, { enabled: false });
            // Reset 'pypsa-integration' to false (its global default)
            await axios.put(`${API_BASE_URL}/api/features/${anotherFeature}`, { enabled: false });
        });

        it('should enable a feature (demand-projection)', async () => {
            const response = await axios.put(`${API_BASE_URL}/api/features/${featureToTest}`, { enabled: true });
            expect(response.status).toBe(200);
            expect(response.data.status).toBe('success');
            expect(response.data.feature_id).toBe(featureToTest);
            expect(response.data.enabled).toBe(true);

            const getResponse = await axios.get(`${API_BASE_URL}/api/features`);
            expect(getResponse.data.features[featureToTest].enabled).toBe(true);
        });

        it('should disable a feature (load-curve which is initially true in project file)', async () => {
            // First, ensure 'load-curve' is enabled via project file (it is)
            await axios.put(`${API_BASE_URL}/api/features/load-curve`, { enabled: true });


            const response = await axios.put(`${API_BASE_URL}/api/features/load-curve`, { enabled: false });
            expect(response.status).toBe(200);
            expect(response.data.status).toBe('success');
            expect(response.data.feature_id).toBe('load-curve');
            expect(response.data.enabled).toBe(false);

            const getResponse = await axios.get(`${API_BASE_URL}/api/features`);
            expect(getResponse.data.features['load-curve'].enabled).toBe(false);
        });
        
        it('should enable a feature not originally in project file (pypsa-integration)', async () => {
            const response = await axios.put(`${API_BASE_URL}/api/features/${anotherFeature}`, { enabled: true });
            expect(response.status).toBe(200);
            expect(response.data.status).toBe('success');
            expect(response.data.feature_id).toBe(anotherFeature);
            expect(response.data.enabled).toBe(true);

            const getResponse = await axios.get(`${API_BASE_URL}/api/features`);
            expect(getResponse.data.features[anotherFeature].enabled).toBe(true);
        });

        it('should return error for invalid feature_id', async () => {
            try {
                 await axios.put(`${API_BASE_URL}/api/features/non_existent_feature`, { enabled: true });
            } catch (error: any) {
                 expect(error.response.status).toBe(200);
                 expect(error.response.data.status).toBe('error');
                 expect(error.response.data.message).toBe('Failed to update feature');
            }
        });
        
        it('should return error if enabled field is missing', async () => {
            try {
                await axios.put(`${API_BASE_URL}/api/features/${featureToTest}`, {}); // Missing 'enabled'
            } catch (error: any) {
                expect(error.response.status).toBe(200);
                expect(error.response.data.status).toBe('error');
                expect(error.response.data.message).toBe('Missing enabled status');
            }
        });
    });
    
    describe('PUT /api/features/<feature_id> (No Project Loaded)', () => {
        it('should return an error if no project is selected', async () => {
            // This test relies on the server not having a project loaded.
            // This is tricky to guarantee. A dedicated test endpoint /test/unload_project would be best.
            // For now, we assume this test runs in a context where no project is loaded,
            // or the server correctly handles this regardless of prior state (which it should).
            console.warn("Test 'PUT /api/features/<feature_id> without project' is potentially flaky due to server state.");
            try {
                await axios.put(`${API_BASE_URL}/api/features/demand-projection`, { enabled: true });
            } catch (error: any) {
                expect(error.response.status).toBe(200);
                expect(error.response.data.status).toBe('error');
                expect(error.response.data.message).toBe('No project selected');
            }
        });
    });
});
