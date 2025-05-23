module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node', // Use 'jsdom' for frontend tests that need a DOM
  setupFilesAfterEnv: ['./tests/setupFetchMock.ts'], // For jest-fetch-mock
  moduleNameMapper: {
    // If you have module aliases in tsconfig.json, map them here
    // Example: "^@/(.*)$": "<rootDir>/src/$1"
  },
  // Automatically clear mock calls and instances between every test
  clearMocks: true,
};
