import { defineAsyncComponent } from "vue";

import DateField from "./DateField.vue";
import DateTimeField from "./DateTimeField.vue";
import FileField from "./FileField.vue";
import ImageField from "./ImageField.vue";
import JsonField from "./JsonField.vue";
import LookupField from "./LookupField.vue";
import NumberField from "./NumberField.vue";
import PasswordField from "./PasswordField.vue";
import SelectField from "./SelectField.vue";
import SwitchField from "./SwitchField.vue";
import TextField from "./TextField.vue";
import TextareaField from "./TextareaField.vue";
import TimezoneField from "./TimezoneField.vue";

// The editor carries its own bundle, so it only reaches the browser on a screen that has one.
const HtmlField = defineAsyncComponent(() => import("./HtmlField.vue"));

// What draws each kind of data, which is a closed set: a type with nothing here is a field that draws nothing at all.
export const FIELD_COMPONENTS = {
    text: TextField,
    textarea: TextareaField,
    number: NumberField,
    switch: SwitchField,
    select: SelectField,
    lookup: LookupField,
    datetime: DateTimeField,
    date: DateField,
    json: JsonField,
    html: HtmlField,
    image: ImageField,
    file: FileField,
    password: PasswordField,
    timezone: TimezoneField,
};
