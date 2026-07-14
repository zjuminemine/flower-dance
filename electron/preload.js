const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    getApiUrl: async () => {
        return await ipcRenderer.invoke('get-api-url');
    },
    showErrorDialog: async (message) => {
        await ipcRenderer.invoke('show-error-dialog', message);
    },
    showMessageDialog: async (title, message) => {
        await ipcRenderer.invoke('show-message-dialog', title, message);
    },
});