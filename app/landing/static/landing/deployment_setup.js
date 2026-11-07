const folderInput = document.querySelector('#project-folder');
const folderStatus = document.querySelector('#folder-selection-status');
const folderHint = document.querySelector('#folder-selection-hint');
const removeFolderButton = document.querySelector('#remove-project-folder');
const repositoryInput = document.querySelector('#repository-url');
const repositoryEntry = document.querySelector('#repository-entry');
const addRepositoryButton = document.querySelector('#add-repository');
const repositorySelected = document.querySelector('#repository-selected');
const repositoryValue = document.querySelector('#repository-value');
const removeRepositoryButton = document.querySelector('#remove-repository');
const sourceStatus = document.querySelector('#project-source-status');
const sourceStatusText = document.querySelector('#project-source-status-text');
const serverHostInput = document.querySelector('#server-host');
const sshUserInput = document.querySelector('#ssh-user');
const sshPortInput = document.querySelector('#ssh-port');
const deployPathInput = document.querySelector('#deploy-path');
const serverTargetSummary = document.querySelector('#server-target-summary');

let selectedRepository = '';
let folderErrorTimeout;
const touchedServerFields = new WeakSet();
const addedServerValues = new Map();
const serverFieldDetails = {
    host: { input: serverHostInput, key: 'server_host' },
    username: { input: sshUserInput, key: 'ssh_username' },
    port: { input: sshPortInput, key: 'ssh_port' },
    path: { input: deployPathInput, key: 'application_path' },
};

function renderServerTargetSummary() {
    if (!serverTargetSummary) return;

    serverTargetSummary.replaceChildren();

    if (addedServerValues.size === 0) {
        const emptyRow = document.createElement('div');
        emptyRow.className = 'deployment_server-summary-empty';
        const key = document.createElement('dt');
        key.textContent = 'Status';
        const value = document.createElement('dd');
        value.textContent = 'No server details added';
        emptyRow.append(key, value);
        serverTargetSummary.append(emptyRow);
        return;
    }

    addedServerValues.forEach((value, key) => {
        const row = document.createElement('div');
        const summaryKey = document.createElement('dt');
        const summaryValue = document.createElement('dd');
        summaryKey.textContent = key;
        summaryValue.textContent = value;
        row.append(summaryKey, summaryValue);
        serverTargetSummary.append(row);
    });
}

document.querySelectorAll('[data-server-field]').forEach((button) => {
    const field = serverFieldDetails[button.dataset.serverField];
    if (!field?.input) return;

    if (button.dataset.serverField === 'path') {
        button.disabled = !field.input.value.trim();
        field.input.addEventListener('input', () => {
            if (!addedServerValues.has(field.key)) {
                button.disabled = !field.input.value.trim();
            }
        });
    }

    button.addEventListener('click', () => {
        const fieldName = button.dataset.serverField;

        if (addedServerValues.has(field.key)) {
            addedServerValues.delete(field.key);
            field.input.disabled = false;
            button.textContent = 'Add';
            button.setAttribute('aria-pressed', 'false');
            if (fieldName === 'path') button.disabled = !field.input.value.trim();
            renderServerTargetSummary();
            return;
        }

        touchedServerFields.add(field.input);
        validateServerField(field.input);
        if (!field.input.checkValidity()) {
            return;
        }

        const value = field.input.value.trim();
        if (!value) return;

        addedServerValues.set(field.key, value);
        field.input.disabled = true;
        button.textContent = 'Remove';
        button.disabled = false;
        button.setAttribute('aria-pressed', 'true');
        renderServerTargetSummary();
    });
});

function isValidServerHost(value) {
    const host = value.trim();
    const ipv4Parts = host.split('.');

    if (ipv4Parts.length === 4 && ipv4Parts.every((part) => /^\d+$/.test(part))) {
        return ipv4Parts.every((part) => Number(part) <= 255);
    }

    if (!host || host.length > 253 || /^[\d.]+$/.test(host)) return false;

    const hostname = host.endsWith('.') ? host.slice(0, -1) : host;
    const labels = hostname.split('.');

    return labels.every((label) => label.length <= 63
        && /^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$/.test(label));
}

function validateServerField(input) {
    if (!input) return true;

    const value = input.value.trim();
    let error = '';

    if (input === serverHostInput) {
        if (!value) {
            error = 'Enter the server IP address or hostname.';
        } else if (!isValidServerHost(value)) {
            error = 'Enter a valid IPv4 address (each number 0–255) or hostname.';
        }
    } else if (input === sshUserInput) {
        if (!value) {
            error = 'Enter the SSH username.';
        } else if (value.length > 32 || !/^[A-Za-z_][A-Za-z0-9_-]*\$?$/.test(value)) {
            error = 'Use 1–32 characters: start with a letter or _, then use letters, numbers, _ or -.';
        }
    } else if (input === sshPortInput) {
        const port = input.valueAsNumber;
        if (!Number.isInteger(port) || port < 1 || port > 65535) {
            error = 'Enter a whole port number from 1 to 65535.';
        }
    } else if (input === deployPathInput && value) {
        const normalizedPath = value.endsWith('/') ? value.slice(0, -1) : value;
        const isAbsolutePath = normalizedPath.startsWith('/') && normalizedPath !== '/';
        const isHomePath = normalizedPath.startsWith('~/') && normalizedPath !== '~/';
        const pathParts = normalizedPath.replace(/^~\//, '').replace(/^\//, '').split('/');
        const hasSafePathParts = pathParts.every((part) => /^[A-Za-z0-9._-]+$/.test(part)
            && part !== '.'
            && part !== '..');

        if ((!isAbsolutePath && !isHomePath) || !hasSafePathParts) {
            error = 'Use an absolute path such as /opt/my-app or a home path such as ~/apps/my-app.';
        }
    }

    input.setCustomValidity(error);
    const errorMessage = document.querySelector(`#${input.id}-error`);
    if (errorMessage) {
        errorMessage.textContent = error;
        errorMessage.hidden = !error;
    }
    input.classList.toggle('is-invalid', Boolean(error));
    input.setAttribute('aria-invalid', String(Boolean(error)));
    return !error;
}

[serverHostInput, sshUserInput, sshPortInput, deployPathInput].forEach((input) => {
    if (!input) return;

    input.addEventListener('blur', () => {
        touchedServerFields.add(input);
        validateServerField(input);
    });

    input.addEventListener('input', () => {
        if (touchedServerFields.has(input)) validateServerField(input);
    });
});

function isGitHubRepositoryUrl(value) {
    try {
        const url = new URL(value);
        const pathParts = url.pathname.split('/').filter(Boolean);
        const [owner, repository] = pathParts;
        const repositoryName = repository?.replace(/\.git$/i, '');

        return url.protocol === 'https:'
            && url.hostname === 'github.com'
            && !url.port
            && !url.username
            && !url.password
            && !url.search
            && !url.hash
            && pathParts.length === 2
            && /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$/.test(owner)
            && /^[A-Za-z0-9._-]+$/.test(repositoryName)
            && repositoryName !== '.'
            && repositoryName !== '..';
    } catch {
        return false;
    }
}

function updateSourceStatus(message) {
    if (sourceStatusText) {
        sourceStatusText.textContent = message;
    }
    sourceStatus?.classList.toggle('is-selected', message.startsWith('Project source added'));
}

function clearFolderSelection() {
    if (!folderInput || !folderStatus || !removeFolderButton) return;

    clearTimeout(folderErrorTimeout);
    folderInput.value = '';
    folderStatus.textContent = 'No folder selected';
    folderStatus.classList.remove('is-error');
    if (folderHint) folderHint.hidden = false;
    removeFolderButton.hidden = true;
}

function clearRepositorySelection() {
    selectedRepository = '';

    if (repositoryInput) repositoryInput.value = '';
    if (repositoryValue) repositoryValue.textContent = '';
    if (repositoryEntry) repositoryEntry.hidden = false;
    if (repositorySelected) repositorySelected.hidden = true;
}

if (folderInput && folderStatus && removeFolderButton) {
    folderInput.addEventListener('change', () => {
        clearTimeout(folderErrorTimeout);
        folderStatus.classList.remove('is-error');
        if (folderHint) folderHint.hidden = false;

        const selectedFiles = Array.from(folderInput.files || []);

        if (selectedFiles.length === 0) {
            folderStatus.textContent = 'No folder selected';
            removeFolderButton.hidden = true;
            updateSourceStatus(selectedRepository ? 'Project source added · GitHub repository' : 'No project source added');
            return;
        }

        const containsPythonFile = selectedFiles.some((file) => file.name.toLowerCase().endsWith('.py'));

        if (!containsPythonFile) {
            folderStatus.textContent = 'No .py files found. Choose a Python project folder.';
            folderStatus.classList.add('is-error');
            folderInput.value = '';
            removeFolderButton.hidden = true;
            if (folderHint) folderHint.hidden = true;
            updateSourceStatus(selectedRepository ? 'Project source added · GitHub repository' : 'No project source added');

            folderErrorTimeout = setTimeout(() => {
                folderStatus.textContent = 'No folder selected';
                folderStatus.classList.remove('is-error');
                if (folderHint) folderHint.hidden = false;
            }, 5000);
            return;
        }

        clearRepositorySelection();
        const firstFilePath = selectedFiles[0].webkitRelativePath || selectedFiles[0].name;
        const folderName = firstFilePath.split('/')[0];
        const fileLabel = selectedFiles.length === 1 ? 'file' : 'files';

        folderStatus.textContent = `${folderName} · ${selectedFiles.length} ${fileLabel} selected`;
        removeFolderButton.hidden = false;
        updateSourceStatus(`Project source added · Folder: ${folderName}`);
    });

    removeFolderButton.addEventListener('click', () => {
        clearFolderSelection();
        updateSourceStatus(selectedRepository ? 'Project source added · GitHub repository' : 'No project source added');
    });
}

if (repositoryInput && repositoryEntry && addRepositoryButton && repositorySelected && repositoryValue && removeRepositoryButton) {
    addRepositoryButton.addEventListener('click', () => {
        const repositoryUrl = repositoryInput.value.trim();

        if (!repositoryInput.checkValidity() || !isGitHubRepositoryUrl(repositoryUrl)) {
            repositoryInput.setCustomValidity('Enter a GitHub repository URL, such as https://github.com/owner/project.');
            repositoryInput.reportValidity();
            return;
        }

        repositoryInput.setCustomValidity('');
        clearFolderSelection();
        selectedRepository = repositoryUrl;
        repositoryValue.textContent = repositoryUrl;
        repositoryEntry.hidden = true;
        repositorySelected.hidden = false;
        updateSourceStatus('Project source added · GitHub repository');
    });

    repositoryInput.addEventListener('input', () => {
        repositoryInput.setCustomValidity('');
    });

    removeRepositoryButton.addEventListener('click', () => {
        clearRepositorySelection();
        updateSourceStatus(folderInput?.files.length ? 'Project source added · Folder' : 'No project source added');
    });
}
