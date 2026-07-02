/**
 * ILD Range module — first registered processing module.
 *
 * Handles International Long Distance PRR (PeerRouteRule) + RBAR
 * (AddressRange) change requests against DRA instances.
 */
import { Globe2 } from 'lucide-react'

const ildModule = {
  id: 'ILD',
  label: 'ILD Range',
  description:
    'PRR (s6a/s6d) and RBAR IMSI-range changes across BM-DRA / V-DRA instances.',
  icon: Globe2,
  accept: '.csv',
  csvColumns: ['Country', 'Operator', 'MCC', 'MNC', 'Realm', 'PRT Rule', 'Range', 'ACTION'],
  // No module-specific extra inputs yet — slot stays available:
  WizardExtra: null,
}

export default ildModule
