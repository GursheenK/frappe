import './index.css'

import { createApp } from 'vue'
import router from './router'
import App from './App.vue'

import { Button, setConfig, frappeRequest, resourcesPlugin } from 'frappe-ui'
import Icon from "@/components/Icon.vue"

let app = createApp(App)

setConfig('resourceFetcher', frappeRequest)

app.use(router)
app.use(resourcesPlugin)

app.component('Button', Button)
app.component("Icon", Icon)
app.mount('#app')
