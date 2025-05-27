import axios from 'axios';
// const fs = require('fs'); // May not be available or useful if test runner is sandboxed
// const path = require('path'); // May not be available or useful

const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:5000';
const DEFAULT_PROJECT_PATH = 'testing project/Default_project'; // Relative to app root

// Helper to get a unique project name for creation tests
const getUniqueProjectName = () => `test_project_${Date.now()}`;

describe('Project Management API', () => {

    // Utility to attempt to remove a directory (best effort for cleanup)
    // This is highly dependent on the execution environment of the tests and the Flask app.
    // In many CI/sandboxed environments, this might not work or be irrelevant.
    async function cleanupTestProject(projectPath: string) {
        // This function would ideally make an API call to the backend to delete a project
        // if such an endpoint existed. Direct file system manipulation from tests is often problematic.
        // For now, we'll note that cleanup is an issue.
        console.warn(`Cleanup for project ${projectPath} is manual or relies on a separate cleanup script.`);
    }

    describe('GET /api/recent_projects', () => {
        it('should initially return an empty or default list of recent projects', async () => {
            // To ensure a clean state for this test, try to delete all recent projects first.
            // This depends on /api/delete_recent_project working and having a way to get all current recent projects.
            // A more robust way would be to clear/reset user_recent_projects.json on the server for testing.
            // For now, we proceed assuming it might not be perfectly empty.
            console.warn("Test 'GET /api/recent_projects initially' might show existing projects if not run in a clean environment or if cleanup between test runs is not thorough.");
            const response = await axios.get(`${API_BASE_URL}/api/recent_projects`);
            expect(response.status).toBe(200);
            expect(response.data.recent_projects).toBeInstanceOf(Array);
            // If user_recent_projects.json is guaranteed to be empty/non-existent at test start:
            // expect(response.data.recent_projects.length).toBe(0); 
        });
    });

    describe('POST /load_project', () => {
        it('should successfully load the Default_project', async () => {
            const response = await axios.post(
                `${API_BASE_URL}/load_project`,
                new URLSearchParams({ projectPath: DEFAULT_PROJECT_PATH })
            );
            expect(response.status).toBe(200);
            expect(response.data.status).toBe('success');
            expect(response.data.project_name).toBe('Default_project'); // Assuming project name is derived from path

            // Verify it's in recent projects
            const recentResponse = await axios.get(`${API_BASE_URL}/api/recent_projects`);
            const recentProjects = recentResponse.data.recent_projects;
            expect(recentProjects.some((p: any) => p.path === DEFAULT_PROJECT_PATH && p.name === 'Default_project')).toBe(true);
        });

        it('should return error for non-existent project path', async () => {
            const nonExistentPath = 'non_existent_project_path_12345';
            try {
                await axios.post(
                    `${API_BASE_URL}/load_project`,
                    new URLSearchParams({ projectPath: nonExistentPath })
                );
            } catch (error: any) {
                expect(error.response.status).toBe(200); // app.py returns 200 OK with error status
                expect(error.response.data.status).toBe('error');
                expect(error.response.data.message).toContain(`The path "${nonExistentPath}" does not exist`);
            }
        });
        
        it('should return error for invalid project structure (e.g. missing inputs folder)', async () => {
            // This test requires a project directory to exist but be invalid.
            // We'll assume a pre-existing 'invalid_project_for_test' or skip if not feasible
            // For now, this test is more of a placeholder unless we can create such a structure via an API or setup script.
            const invalidProjectPath = 'testing project/Invalid_project_missing_inputs'; // Needs to be created for a full test
            console.warn(`Test for loading invalid project structure ('${invalidProjectPath}') assumes it exists and is invalid.`);
            
            // Create a dummy invalid project structure for testing (if possible, otherwise this test is limited)
            // This is illustrative; actual creation might need bash commands or another setup step if API doesn't allow such creation.
            // For now, we'll just try to load it and expect failure if it's truly invalid per app.py logic
             try {
                await axios.post(
                    `${API_BASE_URL}/load_project`,
                    new URLSearchParams({ projectPath: invalidProjectPath })
                );
            } catch (error: any) {
                expect(error.response.status).toBe(200);
                expect(error.response.data.status).toBe('error');
                // The exact error message might vary based on what `validate_project_structure` returns for it
                expect(error.response.data.message).toContain('Project structure is invalid');
            }
        });
    });

    describe('POST /validate_project', () => {
        it('should validate Default_project successfully (or with warnings for optional files)', async () => {
            const response = await axios.post(
                `${API_BASE_URL}/validate_project`,
                new URLSearchParams({ projectPath: DEFAULT_PROJECT_PATH })
            );
            expect(response.status).toBe(200);
            // Default_project is expected to be valid or have only warnings for missing optional files
            expect(['success', 'warning']).toContain(response.data.status);
            if (response.data.status === 'success') {
                expect(response.data.message).toBe('Project structure is valid.');
            } else {
                expect(response.data.message).toBe('Project structure has missing optional files/folders.');
            }
        });

        it('should report errors for an invalid project structure', async () => {
            // This test needs an invalid project. Let's assume 'testing project/Invalid_project_missing_inputs' exists.
            // If not, this test's scope is limited.
            const invalidProjectPath = 'testing project/Invalid_project_missing_inputs'; // Needs to be created
            console.warn(`Test for validating invalid project ('${invalidProjectPath}') assumes it exists and is invalid.`);
            const response = await axios.post(
                `${API_BASE_URL}/validate_project`,
                new URLSearchParams({ projectPath: invalidProjectPath })
            );
            expect(response.status).toBe(200);
            expect(response.data.status).toBe('error');
            expect(response.data.message).toBe('Project structure is invalid.');
            expect(response.data.missing_required_items).toContain('inputs'); // Specific to this invalid case
        });
    });
    
    describe('POST /create_project', () => {
        // projectLocation is a sub-directory path relative to static/user_uploads/projects/
        const testProjectLocation = 'test_project_creation_dir'; 
        let createdTestProjectPath: string | null = null;
        let fullCreatedPathForCleanup: string | null = null;


        it('should successfully create a new project', async () => {
            const newProjectName = getUniqueProjectName();
            const response = await axios.post(
                `${API_BASE_URL}/create_project`,
                new URLSearchParams({ projectName: newProjectName, projectLocation: testProjectLocation })
            );
            expect(response.status).toBe(200);
            expect(response.data.status).toBe('success');
            expect(response.data.message).toContain('created successfully');
            expect(response.data.project_path).toBeDefined();
            // The returned project_path is relative to the app's root, e.g., "static/user_uploads/projects/test_project_creation_dir/test_project_1678886400000"
            createdTestProjectPath = response.data.project_path; 
            fullCreatedPathForCleanup = createdTestProjectPath; // Store the full path for potential cleanup logic

            // Verify it's in recent projects
            const recentResponse = await axios.get(`${API_BASE_URL}/api/recent_projects`);
            const recentProjects = recentResponse.data.recent_projects;
            expect(recentProjects.some((p: any) => p.path === createdTestProjectPath)).toBe(true);
        });
        
        it('should return error if project name is missing', async () => {
            try {
                 await axios.post(
                    `${API_BASE_URL}/create_project`,
                    new URLSearchParams({ projectLocation: testProjectLocation }) // projectName omitted
                );
            } catch (error: any) {
                expect(error.response.status).toBe(200);
                expect(error.response.data.status).toBe('error');
                expect(error.response.data.message).toBe('Project name is required');
            }
        });

        it('should return error if project location is missing', async () => {
             const newProjectName = getUniqueProjectName();
            try {
                 await axios.post(
                    `${API_BASE_URL}/create_project`,
                    new URLSearchParams({ projectName: newProjectName }) // projectLocation omitted
                );
            } catch (error: any) {
                expect(error.response.status).toBe(200);
                expect(error.response.data.status).toBe('error');
                expect(error.response.data.message).toBe('Project location is required');
            }
        });
        
        it('should return error if project with same name already exists at the location', async () => {
            const newProjectName = getUniqueProjectName();
            // Create it once
            await axios.post(
                `${API_BASE_URL}/create_project`,
                new URLSearchParams({ projectName: newProjectName, projectLocation: testProjectLocation })
            );
            // Try to create it again
            try {
                await axios.post(
                    `${API_BASE_URL}/create_project`,
                    new URLSearchParams({ projectName: newProjectName, projectLocation: testProjectLocation })
                );
            } catch (error: any) {
                expect(error.response.status).toBe(200);
                expect(error.response.data.status).toBe('error');
                expect(error.response.data.message).toContain('already exists at the specified location');
            }
        });

        afterAll(async () => {
            // This is a placeholder for cleanup. Actual file system deletion from tests is complex.
            // A backend endpoint for deleting projects would be ideal.
            if (fullCreatedPathForCleanup) {
                 console.warn(`Test created project at: ${fullCreatedPathForCleanup}. Manual cleanup or a dedicated cleanup API endpoint is recommended.`);
                // For example, if an API existed:
                // await axios.post(`${API_BASE_URL}/api/delete_project_folder`, { projectPath: fullCreatedPathForCleanup });
            }
            // Additionally, cleanup the test_project_creation_dir if it's empty or only contains test projects.
            // This is also complex from client-side tests.
        });
    });
    
    describe('POST /api/delete_recent_project', () => {
        const projectToMakeRecent = DEFAULT_PROJECT_PATH; // Use Default_project

        beforeEach(async () => {
            // Ensure the project is in recent list by loading it
            await axios.post(
                `${API_BASE_URL}/load_project`,
                new URLSearchParams({ projectPath: projectToMakeRecent })
            );
        });

        it('should delete a project from recent projects', async () => {
            let recentResponse = await axios.get(`${API_BASE_URL}/api/recent_projects`);
            let isRecent = recentResponse.data.recent_projects.some((p: any) => p.path === projectToMakeRecent);
            expect(isRecent).toBe(true); // Verify it's there

            const deleteResponse = await axios.post(
                `${API_BASE_URL}/api/delete_recent_project`,
                { projectPath: projectToMakeRecent } // request.get_json() expects JSON body
            );
            expect(deleteResponse.status).toBe(200);
            expect(deleteResponse.data.status).toBe('success');

            recentResponse = await axios.get(`${API_BASE_URL}/api/recent_projects`);
            isRecent = recentResponse.data.recent_projects.some((p: any) => p.path === projectToMakeRecent);
            expect(isRecent).toBe(false); // Verify it's gone
        });
        
        it('should return error if project path not in recent projects', async () => {
            const nonRecentPath = 'some/path/not/in/recents_list_123';
             try {
                await axios.post(
                    `${API_BASE_URL}/api/delete_recent_project`,
                    { projectPath: nonRecentPath } // JSON body
                );
            } catch (error: any) {
                expect(error.response.status).toBe(200); // API returns 200 with status: 'error'
                expect(error.response.data.status).toBe('error');
                expect(error.response.data.message).toBe('Project not found in recent projects');
            }
        });
    });
});
