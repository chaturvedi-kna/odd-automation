/**
 * Module dispatcher for the request wizard: /requests/new/:moduleId renders
 * the generic RequestWizard configured by the registered module. Unknown
 * module ids redirect to the default module.
 */
import { useParams, Navigate } from 'react-router-dom'
import { getModule, defaultModule } from '../modules/registry'
import RequestWizard from '../components/RequestWizard'

export default function NewRequest() {
  const { moduleId } = useParams()
  const mod = getModule(moduleId)

  if (!mod) {
    return <Navigate to={`/requests/new/${defaultModule().id.toLowerCase()}`} replace />
  }
  return <RequestWizard module={mod} />
}
