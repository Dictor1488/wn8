from .translations import Translator
from ..utils import logger

PARAM_REGISTRY = {}


def toJson(obj):
    import json
    return json.dumps(obj, ensure_ascii=False)


def toBool(value):
    return str(value).lower() == "true"


def clamp(minValue, value, maxValue):
    if minValue is not None:
        value = max(minValue, value)
    if maxValue is not None:
        value = min(value, maxValue)
    return value


def createTooltip(header=None, body=None, note=None, attention=None):
    resStr = ''
    if header is not None:
        resStr += '{HEADER}%s{/HEADER}' % header
    if body is not None:
        resStr += '{BODY}%s{/BODY}' % body
    if note is not None:
        resStr += '{NOTE}%s{/NOTE}' % note
    if attention is not None:
        resStr += '{ATTENTION}%s{/ATTENTION}' % attention
    return resStr


class BaseParameter(object):

    def __init__(self, path, defaultValue, disabledValue=None):
        self.name = path[-1]
        self.path = path
        self.tokenName = "-".join(self.path)

        self.value = defaultValue
        self.defaultValue = defaultValue
        self.disabledValue = disabledValue if disabledValue is not None else defaultValue

        PARAM_REGISTRY[self.tokenName] = self

    def __call__(self):
        from ..settings import g_config
        if hasattr(g_config, 'configParams') and hasattr(g_config.configParams, 'enabled'):
            if not g_config.configParams.enabled.value:
                return self.disabledValue
        return self.value

    @property
    def jsonValue(self):
        return self.toJsonValue(self.value)

    @jsonValue.setter
    def jsonValue(self, jsonValue):
        try:
            self.value = self.fromJsonValue(jsonValue)
        except Exception as e:
            logger.error("Error saving parameter %s with jsonValue %s: %s",
                self.tokenName, jsonValue, str(e))

    @property
    def msaValue(self):
        return self.toMsaValue(self.value)

    @msaValue.setter
    def msaValue(self, msaValue):
        try:
            self.value = self.fromMsaValue(msaValue)
        except Exception as e:
            logger.error("Error saving parameter %s with msaValue %s: %s",
                self.tokenName, msaValue, str(e))

    @property
    def defaultMsaValue(self):
        return self.toMsaValue(self.defaultValue)

    @property
    def defaultJsonValue(self):
        return self.toJsonValue(self.defaultValue)

    def toMsaValue(self, value):
        raise NotImplementedError()

    def fromMsaValue(self, msaValue):
        raise NotImplementedError()

    def toJsonValue(self, value):
        raise NotImplementedError()

    def fromJsonValue(self, jsonValue):
        raise NotImplementedError()

    def renderParam(self, header, body=None, note=None, attention=None):
        raise NotImplementedError()


class CheckboxParameter(BaseParameter):

    def __init__(self, path, defaultValue=None, disabledValue=None):
        super(CheckboxParameter, self).__init__(path, defaultValue, disabledValue)

    def toMsaValue(self, value):
        return value

    def fromMsaValue(self, msaValue):
        return msaValue

    def toJsonValue(self, value):
        return toJson(value)

    def fromJsonValue(self, jsonValue):
        return toBool(jsonValue)

    def renderParam(self, header, body=None, note=None, attention=None):
        currentValue = self.toMsaValue(self.value)
        return {
            "type": "CheckBox",
            "text": header,
            "varName": self.tokenName,
            "value": currentValue,
            "tooltip": createTooltip(
                header="{} ({}: {})".format(
                    header,
                    Translator.DEFAULT_VALUE,
                    Translator.CHECKED if self.defaultValue else Translator.UNCHECKED
                ),
                body=body,
                note=note,
                attention=attention
            )
        }


class OptionItem(object):

    def __init__(self, value, msaValue, displayName):
        self.value = value
        self.msaValue = msaValue
        self.displayName = displayName


class DropdownParameter(BaseParameter):

    def __init__(self, path, options, defaultValue, disabledValue=None):
        super(DropdownParameter, self).__init__(path, defaultValue, disabledValue)
        self.options = options

    def toMsaValue(self, value):
        for i, option in enumerate(self.options):
            if option.value == value:
                return i
        return 0

    def fromMsaValue(self, msaValue):
        try:
            index = int(msaValue)
            if 0 <= index < len(self.options):
                return self.options[index].value
        except (ValueError, TypeError):
            pass
        return self.defaultValue

    def toJsonValue(self, value):
        return toJson(value)

    def fromJsonValue(self, jsonValue):
        option = self.getOptionByValue(jsonValue)
        if option is None:
            raise Exception("Invalid value {} for config param {}".format(jsonValue, self.tokenName))
        return option.value

    def getOptionByValue(self, value):
        foundOptions = [option for option in self.options if option.value == value]
        return foundOptions[0] if len(foundOptions) > 0 else None

    def getOptionByMsaValue(self, msaValue):
        try:
            index = int(msaValue)
            if 0 <= index < len(self.options):
                return self.options[index]
        except (ValueError, TypeError):
            pass
        return self.getOptionByValue(self.defaultValue)

    def renderParam(self, header, body=None, note=None, attention=None):
        currentValue = self.toMsaValue(self.value)
        return {
            "type": "Dropdown",
            "text": header,
            "varName": self.tokenName,
            "value": currentValue,
            "options": [
                {"label": option.displayName} for option in self.options
            ],
            "tooltip": createTooltip(
                header="{} ({}: {})".format(
                    header,
                    Translator.DEFAULT_VALUE,
                    self.getOptionByValue(self.defaultValue).displayName
                ),
                body=body,
                note=note,
                attention=attention
            ),
            "width": 200
        }


class TextInputParameter(BaseParameter):

    def __init__(self, path, defaultValue='', disabledValue=None):
        super(TextInputParameter, self).__init__(path, defaultValue, disabledValue)

    def toMsaValue(self, value):
        return value if value is not None else ''

    def fromMsaValue(self, msaValue):
        if msaValue is None:
            return self.defaultValue
        return str(msaValue)

    def toJsonValue(self, value):
        return toJson(value)

    def fromJsonValue(self, jsonValue):
        return jsonValue if jsonValue is not None else self.defaultValue

    def renderParam(self, header, body=None, note=None, attention=None):
        return {
            "type": "TextInput",
            "text": header,
            "varName": self.tokenName,
            "value": self.toMsaValue(self.value),
            "tooltip": createTooltip(
                header="{} ({}: {})".format(
                    header,
                    Translator.DEFAULT_VALUE,
                    self.defaultValue or "''"
                ),
                body=body,
                note=note,
                attention=attention
            ),
            "width": 250
        }
