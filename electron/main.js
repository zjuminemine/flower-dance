const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const isDev = require('electron-is-dev');

let mainWindow = null;
let backendProcess = null;
const BACKEND_PORT = 8000;

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        minWidth: 1000,
        minHeight: 700,
        title: '朝花夕拾 Flower Dance',
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false,
            enableRemoteModule: false,
            sandbox: false,
            webSecurity: false,
        },
        frame: true,
        transparent: false,
    });

    mainWindow.loadFile('frontend/index.html');

    if (isDev) {
        mainWindow.webContents.openDevTools({ mode: 'detach' });
    }

    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

function startBackend() {
    return new Promise((resolve, reject) => {
        const userLocalBin = process.platform === 'darwin' 
            ? '/Users/stephenwong/.local/bin' 
            : process.platform === 'win32' 
                ? `${process.env.USERPROFILE}\\AppData\\Local\\Packages\\PythonSoftwareFoundation.Python.3.9_qbz5n2kfra8p0\\LocalCache\\local-packages\\Python39\\Scripts`
                : '/home/stephenwong/.local/bin';
        
        const pythonPath = process.platform === 'darwin' 
            ? '/Users/stephenwong/opt/anaconda3/bin/python3' 
            : process.platform === 'win32' 
                ? 'python' 
                : 'python3';

        const backendDir = path.join(__dirname, '..', 'backend');
        
        const envPath = userLocalBin + (process.env.PATH ? (process.platform === 'win32' ? ';' : ':') + process.env.PATH : '');
        
        backendProcess = spawn(pythonPath, ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', BACKEND_PORT], {
            cwd: backendDir,
            stdio: ['pipe', 'pipe', 'pipe'],
            env: {
                ...process.env,
                PATH: envPath,
                PYTHONPATH: backendDir + (process.env.PYTHONPATH ? ':' + process.env.PYTHONPATH : ''),
            },
        });

        backendProcess.stdout.on('data', (data) => {
            const output = data.toString();
            console.log('[Backend]', output.trim());
            if (output.includes('Uvicorn running')) {
                resolve();
            }
        });

        backendProcess.stderr.on('data', (data) => {
            const error = data.toString();
            console.error('[Backend Error]', error.trim());
        });

        backendProcess.on('error', (err) => {
            console.error('Failed to start backend:', err);
            reject(err);
        });

        backendProcess.on('close', (code) => {
            console.log(`Backend process exited with code ${code}`);
        });

        setTimeout(() => {
            resolve();
        }, 5000);
    });
}

ipcMain.handle('get-api-url', () => {
    return `http://127.0.0.1:${BACKEND_PORT}`;
});

ipcMain.handle('show-error-dialog', async (_, message) => {
    await dialog.showErrorBox('错误', message);
});

ipcMain.handle('show-message-dialog', async (_, title, message) => {
    await dialog.showMessageBox(mainWindow, {
        type: 'info',
        title,
        message,
    });
});

app.whenReady().then(async () => {
    try {
        await startBackend();
        createWindow();
    } catch (err) {
        console.error('Application startup failed:', err);
        dialog.showErrorBox('启动失败', `无法启动后端服务：${err.message}\n\n请确保已安装 Python 3.8+ 和必要依赖。`);
        app.quit();
    }
});

app.on('window-all-closed', () => {
    if (backendProcess) {
        backendProcess.kill();
    }
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
    }
});