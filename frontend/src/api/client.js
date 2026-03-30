import axios from 'axios';

const API_URL = '/api';

const client = axios.create({
    baseURL: API_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

export const uploadFiles = async (files) => {
    const formData = new FormData();
    files.forEach((file) => {
        formData.append('files', file);
    });

    const response = await client.post('/upload', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
    return response.data; // includes session_folder
};

export const processDocs = async (config) => {
    const response = await client.post('/process-docs', config);
    return response.data; // { message, status: "processing" }
};

export const getDocResult = async (session) => {
    const response = await client.get('/doc-result', { params: { session } });
    return response.data;
};

export const enhanceJson = async (data) => {
    const response = await client.post('/enhance-json', data);
    return response.data;
};

export const getEnhanceResult = async (session) => {
    const response = await client.get('/enhance-result', { params: { session } });
    return response.data;
};

export const generateTestCases = async (config) => {
    const response = await client.post('/generate', config);
    return response.data;
};

export const getFiles = async (session = null) => {
    const params = session ? { session } : {};
    const response = await client.get('/files', { params });
    return response.data;
};

export const getCases = async (session) => {
    const response = await client.get('/cases', { params: { session } });
    return response.data;
};

export const getSessions = async () => {
    const response = await client.get('/sessions');
    return response.data;
};

export const getGenerationStatus = async (session = null) => {
    try {
        const params = session ? { session } : {};
        const response = await client.get('/status', { params });
        return response.data;
    } catch (error) {
        console.error("Error checking status:", error);
        return { state: 'unknown' };
    }
};

export const cancelExecution = (session = null) => {
    // sendBeacon es fiable incluso durante beforeunload/page close
    const params = session ? `?session=${encodeURIComponent(session)}` : '';
    navigator.sendBeacon(`${API_URL}/cancel${params}`);
};

export default client;
