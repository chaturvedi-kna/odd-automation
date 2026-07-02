/**
 * Module registry — the "module slot" pattern.
 *
 * The app core (layout, routing, dashboard, requests, dumps) is module-agnostic.
 * Each processing module (ILD Range today; more tomorrow) registers itself here
 * and contributes:
 *
 *   id            : backend module code sent with POST /requests/ (e.g. "ILD")
 *   label         : human name shown in navigation
 *   description   : one-liner shown on the request wizard
 *   icon          : lucide-react icon component
 *   csvColumns    : expected input CSV columns (shown as upload hint)
 *   accept        : accepted upload file extensions
 *   WizardExtra   : optional React component rendered inside the request wizard
 *                   for module-specific inputs (receives {value, onChange})
 *
 * To add a new module: create src/modules/<id>/index.jsx exporting a module
 * object and add it to the list below. Nothing else in the app changes.
 */
import ildModule from './ild'

const MODULES = [
  ildModule,
]

export function listModules() {
  return MODULES
}

export function getModule(id) {
  return MODULES.find(m => m.id.toLowerCase() === String(id ?? '').toLowerCase()) ?? null
}

export function defaultModule() {
  return MODULES[0]
}
