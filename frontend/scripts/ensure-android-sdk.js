const fs = require('fs');
const path = require('path');

function resolveSdkPath() {
  if (process.env.ANDROID_SDK_ROOT) return process.env.ANDROID_SDK_ROOT;
  if (process.env.ANDROID_HOME) return process.env.ANDROID_HOME;

  if (process.platform === 'win32' && process.env.LOCALAPPDATA) {
    return path.join(process.env.LOCALAPPDATA, 'Android', 'Sdk');
  }

  if (process.platform === 'darwin') {
    return path.join(process.env.HOME || '', 'Library', 'Android', 'sdk');
  }

  return path.join(process.env.HOME || '', 'Android', 'Sdk');
}

function main() {
  const projectRoot = process.cwd();
  const sdkPath = resolveSdkPath();

  if (!sdkPath || !fs.existsSync(sdkPath)) {
    console.error(
      `Android SDK no encontrado. Define ANDROID_SDK_ROOT o ANDROID_HOME.\n` +
        `Ruta intentada: ${sdkPath}`
    );
    process.exit(1);
  }

  const androidDir = path.join(projectRoot, 'android');
  const localPropertiesPath = path.join(androidDir, 'local.properties');
  const normalized = sdkPath.replace(/\\/g, '/');
  const content = `sdk.dir=${normalized}\n`;

  fs.writeFileSync(localPropertiesPath, content, 'utf8');
  console.log(`local.properties actualizado: ${normalized}`);
}

main();
