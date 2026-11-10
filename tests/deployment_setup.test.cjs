const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname, '..', 'app', 'landing', 'static', 'landing', 'deployment_setup.js'), 'utf8');

function makeInput(id, value) {
    return {
        id,
        value,
        valueAsNumber: Number(value),
        addEventListener() {},
        classList: { toggle() {} },
        setAttribute() {},
        setCustomValidity(message) { this.validationMessage = message; },
    };
}

function loadValidation(inputs = {}) {
    const context = {
        URL,
        document: {
            querySelector: (selector) => inputs[selector] || null,
            querySelectorAll: () => [],
        },
    };
    vm.runInNewContext(script, context);
    return context;
}

test('server host accepts IPv4 boundaries and valid DNS names', () => {
    const { isValidServerHost } = loadValidation();

    for (const host of ['0.0.0.0', '255.255.255.255', 'server.example.com', 'my-server']) {
        assert.equal(isValidServerHost(host), true, host);
    }
});

test('server host rejects invalid addresses and host labels', () => {
    const { isValidServerHost } = loadValidation();

    for (const host of ['', '256.1.1.1', '1.2.3', '-server.example.com', 'server..example.com']) {
        assert.equal(isValidServerHost(host), false, host);
    }
});

test('repository URL accepts only clean public GitHub repository paths', () => {
    const { isGitHubRepositoryUrl } = loadValidation();

    assert.equal(isGitHubRepositoryUrl('https://github.com/owner/project'), true);
    assert.equal(isGitHubRepositoryUrl('https://github.com/owner/project.git'), true);
    for (const url of [
        'http://github.com/owner/project',
        'https://github.com.evil.example/owner/project',
        'https://github.com/owner/project/tree/main',
        'https://github.com/owner/project?token=secret',
        'https://github.com/owner/..',
        'not a URL',
    ]) {
        assert.equal(isGitHubRepositoryUrl(url), false, url);
    }
});

test('SSH username and port validation reject unsafe or out-of-range values', () => {
    const username = makeInput('ssh-user', 'deploy-user');
    const port = makeInput('ssh-port', '65535');
    const { validateServerField } = loadValidation({ '#ssh-user': username, '#ssh-port': port });

    assert.equal(validateServerField(username), true);
    assert.equal(validateServerField(port), true);

    username.value = 'deploy;whoami';
    assert.equal(validateServerField(username), false);
    assert.match(username.validationMessage, /start with a letter/);

    port.value = '65536';
    port.valueAsNumber = 65536;
    assert.equal(validateServerField(port), false);
    assert.match(port.validationMessage, /1 to 65535/);
});

test('deployment path validation allows app directories and rejects traversal', () => {
    const deployPath = makeInput('deploy-path', '~/apps/my-project');
    const { validateServerField } = loadValidation({ '#deploy-path': deployPath });

    assert.equal(validateServerField(deployPath), true);
    deployPath.value = '/opt/my-app';
    assert.equal(validateServerField(deployPath), true);
    deployPath.value = '/opt/../etc';
    assert.equal(validateServerField(deployPath), false);
    assert.match(deployPath.validationMessage, /absolute path/);
});
