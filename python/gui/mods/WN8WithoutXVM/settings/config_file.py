import json
import os
from ..utils import logger


class ConfigFile(object):

    def __init__(self, configParams):
        self.configPath = os.path.join('mods', 'configs', 'under_pressure', 'wn8withoutxvm.json')
        self.configParams = configParams
        self._loadedConfigData = None

    def _ensureConfigExists(self):
        try:
            configDir = os.path.dirname(self.configPath)
            if not os.path.exists(configDir):
                os.makedirs(configDir)

            if not os.path.exists(self.configPath):
                return self._createDefaultConfig()
            return True
        except Exception as e:
            logger.error("[ConfigFile] Error ensuring config exists: %s", str(e))
            return False

    def _createDefaultConfig(self):
        try:
            configData = {}
            configItems = self.configParams.items()

            for tokenName, param in configItems.items():
                configData[tokenName] = param.defaultValue

            with open(self.configPath, 'w') as f:
                json.dump(configData, f, indent=4, ensure_ascii=False)

            return os.path.exists(self.configPath)

        except Exception as e:
            logger.error("[ConfigFile] Error creating default config: %s", str(e))
            return False

    def load_config(self):
        try:
            if not self._ensureConfigExists():
                configItems = self.configParams.items()
                for tokenName, param in configItems.items():
                    param.value = param.defaultValue
                return False

            if not os.path.exists(self.configPath):
                return False

            with open(self.configPath, 'r') as f:
                content = f.read().strip()

            if not content:
                if self._createDefaultConfig():
                    with open(self.configPath, 'r') as f:
                        content = f.read().strip()
                else:
                    return False

            configData = json.loads(content)
            self._loadedConfigData = configData

            configItems = self.configParams.items()
            for tokenName, param in configItems.items():
                if tokenName in configData:
                    try:
                        param.value = configData[tokenName]
                    except Exception as e:
                        logger.error("[ConfigFile] Error loading parameter %s: %s", tokenName, str(e))
                        param.value = param.defaultValue
                else:
                    param.value = param.defaultValue

            return True

        except ValueError as e:
            logger.error("[ConfigFile] Invalid JSON in config file: %s", str(e))
            self._loadedConfigData = None
            configItems = self.configParams.items()
            for tokenName, param in configItems.items():
                param.value = param.defaultValue
            return False
        except Exception as e:
            logger.error("[ConfigFile] Error loading config: %s", str(e))
            self._loadedConfigData = None
            configItems = self.configParams.items()
            for tokenName, param in configItems.items():
                param.value = param.defaultValue
            return False

    def save_config(self):
        try:
            configDir = os.path.dirname(self.configPath)
            if not os.path.exists(configDir):
                os.makedirs(configDir)

            configData = {}
            configItems = self.configParams.items()
            for tokenName, param in configItems.items():
                configData[tokenName] = param.value

            with open(self.configPath, 'w') as f:
                json.dump(configData, f, indent=4, ensure_ascii=False)

            self._loadedConfigData = configData
            return os.path.exists(self.configPath)

        except Exception as e:
            logger.error("[ConfigFile] Error saving config: %s", str(e))
            return False

    def exists(self):
        return os.path.exists(self.configPath)

    def getConfigPath(self):
        return self.configPath
