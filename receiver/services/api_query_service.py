"""
API Query Service
Fetches DICOM metadata from ITH API for C-FIND queries when local data is not available.
"""
import logging
from typing import Dict, List, Optional, Any
from receiver.services.ith_api_client import IthAPIClient
from receiver.controllers.phi_resolver import PHIResolver

logger = logging.getLogger(__name__)


class APIQueryService:
    """
    Service for querying DICOM metadata from ITH API.
    Used as fallback when local storage doesn't have the data (e.g., after cleanup).
    """

    def __init__(self, api_client: IthAPIClient, resolver: PHIResolver):
        """
        Initialize API query service.

        Args:
            api_client: IthAPIClient instance
            resolver: PHIResolver for de-anonymization
        """
        self.api_client = api_client
        self.resolver = resolver

    def query_all_patients(self) -> List[Dict[str, Any]]:
        """
        Query all patients (subjects) from API.

        Returns:
            List of patient dictionaries with de-anonymized info
        """
        try:
            logger.info("Querying patients from ITH API...")

            response = self.api_client.list_subjects()
            subjects = response.get('subjects', [])

            logger.info(f"Found {len(subjects)} subjects from API")

            patients = []
            for subject in subjects:
                anonymous_id = subject.get('id', '')
                anonymous_name = subject.get('name', '')

                original = self.resolver.resolve_patient(
                    anonymous_name=anonymous_name,
                    anonymous_id=anonymous_id
                )

                if original:
                    patient_info = {
                        'PatientID': original['original_id'],
                        'PatientName': original['original_name'],
                    }
                    logger.debug(f"De-anonymized: {anonymous_name} → {original['original_name']}")
                else:
                    patient_info = {
                        'PatientID': anonymous_id,
                        'PatientName': anonymous_name,
                    }
                    logger.debug(f"No mapping found, using as-is: {anonymous_name}")

                if subject.get('sessions'):
                    first_session = subject['sessions'][0]
                    if 'metadata' in first_session:
                        metadata = first_session.get('metadata', {})
                        patient_info['PatientBirthDate'] = metadata.get('patient_birth_date', '')
                        patient_info['PatientSex'] = metadata.get('patient_sex', '')

                patients.append(patient_info)

            return patients

        except Exception as e:
            logger.error(f"Error querying patients from API: {e}", exc_info=True)
            return []

    def query_all_studies(self) -> List[Dict[str, Any]]:
        """
        Query all studies (sessions) from API.

        Returns:
            List of study dictionaries with de-anonymized info
        """
        try:
            logger.info("Querying studies from ITH API...")

            response = self.api_client.list_sessions()
            sessions = response.get('sessions', [])

            logger.debug(f"Found {len(sessions)} sessions from API")
            logger.debug(f"Raw API response: {response}")

            for i, session in enumerate(sessions, 1):
                logger.debug(f"Session #{i}:")
                logger.debug(f"ID: {session.get('id', 'N/A')}")
                logger.debug(f"Subject ID: {session.get('subject_id', 'N/A')}")
                logger.debug(f"Metadata: {session.get('metadata', {})}")
                logger.debug(f"Scans: {len(session.get('scans', []))} scans")
                if session.get('scans'):
                    for j, scan in enumerate(session.get('scans', []), 1):
                        logger.debug(f"Scan #{j}: {scan}")

            studies = []
            for idx, session in enumerate(sessions, 1):
                workspace_id = session.get('workspace_id', '')
                subject_id = session.get('subject_id', '')
                session_id = session.get('session_id', '')

                logger.info(f"\n{'='*60}")
                logger.info(f"Processing Session #{idx}: {session_id}")
                logger.info(f"{'='*60}")

                try:
                    logger.info(f"📋 Fetching subject details for subject_id: {subject_id}")
                    subject_response = self.api_client.get_subject(subject_id)

                    logger.info(f"✅ Subject API Response:")
                    logger.info(f"   Full response: {subject_response}")

                    subject_data = subject_response.get('subject', {})
                    demographics = subject_data.get('demographics', {})

                    anonymous_name = subject_data.get('label', '')
                    anonymous_id = anonymous_name if anonymous_name else subject_data.get('subject_identifier', subject_id)
                    patient_birth_date = demographics.get('dob', '')

                    logger.info(f"   Extracted from subject:")
                    logger.info(f"     - Anonymous ID: {anonymous_id}")
                    logger.info(f"     - Anonymous Name: {anonymous_name}")
                    logger.info(f"     - Birth Date: {patient_birth_date}")
                    logger.info(f"     - Demographics: {demographics}")

                    gender = demographics.get('gender')
                    if gender:
                        gender_lower = str(gender).lower()
                        if gender_lower == 'male':
                            patient_sex = 'M'
                        elif gender_lower == 'female':
                            patient_sex = 'F'
                        else:
                            patient_sex = 'O'
                    else:
                        patient_sex = ''

                    logger.info(f"     - Gender: {gender} -> DICOM: {patient_sex}")

                except Exception as e:
                    logger.error(f"❌ Could not fetch subject {subject_id}: {e}", exc_info=True)
                    anonymous_id = subject_id
                    anonymous_name = ''
                    patient_birth_date = ''
                    patient_sex = ''

                logger.info(f"\n🔍 De-anonymizing patient data...")
                original = self.resolver.resolve_patient(
                    anonymous_name=anonymous_name,
                    anonymous_id=anonymous_id
                )

                if original:
                    patient_id = original['original_id']
                    patient_name = original['original_name']
                    logger.info(f"✅ De-anonymized successfully:")
                    logger.info(f"   {anonymous_name} ({anonymous_id}) -> {patient_name} ({patient_id})")
                else:
                    patient_id = anonymous_id
                    patient_name = anonymous_name
                    logger.warning(f"⚠️  No mapping found, using as-is: {anonymous_name} (ID: {anonymous_id})")

                scans = []
                try:
                    logger.info(f"\n📊 Fetching scans for session {session_id}...")
                    scans_response = self.api_client.list_scans(subject_id, session_id)

                    logger.info(f"✅ Scans API Response:")
                    logger.info(f"   Full response: {scans_response}")

                    scans = scans_response.get('scans', [])
                    logger.info(f"   Found {len(scans)} scans")

                    for scan_idx, scan in enumerate(scans, 1):
                        logger.info(f"   Scan #{scan_idx}:")
                        logger.info(f"     - ID: {scan.get('id')}")
                        logger.info(f"     - Type: {scan.get('type')}")
                        logger.info(f"     - Instance count: {scan.get('instance_count', 0)}")

                except Exception as e:
                    logger.error(f"❌ Could not fetch scans for session {session_id}: {e}", exc_info=True)
                    scans = []

                logger.info(f"\n📄 Session Data:")
                logger.info(f"   Raw session object: {session}")

                study_date = session.get('date', '')
                study_time = session.get('time', '')

                logger.info(f"\n📅 Extracting dates/times:")
                logger.info(f"   Session date: {session.get('date')}")
                logger.info(f"   Session time: {session.get('time')}")

                if study_date:
                    study_date = study_date.replace('-', '')

                if study_time:
                    study_time = study_time.replace(':', '')

                if patient_birth_date:
                    patient_birth_date = patient_birth_date.replace('-', '')

                logger.info(f"   DICOM StudyDate: {study_date}")
                logger.info(f"   DICOM StudyTime: {study_time}")
                logger.info(f"   DICOM PatientBirthDate: {patient_birth_date}")

                logger.info(f"\n🏗️  Building study info:")

                study_description = session.get('description') or session.get('label', '')

                institution_name = session.get('institution_name')
                if not institution_name:
                    scanner = session.get('scanner', {})
                    institution_name = scanner.get('identifier', '') if scanner else ''

                study_info = {
                    'PatientID': patient_id,
                    'PatientName': patient_name,
                    'PatientBirthDate': patient_birth_date,
                    'PatientSex': patient_sex,
                    'StudyInstanceUID': session.get('study_instance_uid', ''),
                    'StudyID': session.get('session_id', ''),
                    'StudyDescription': study_description,
                    'StudyDate': study_date,
                    'StudyTime': study_time,
                    'AccessionNumber': session.get('accession_number', '') or '',
                    'InstitutionName': institution_name or '',
                    'ModalitiesInStudy': session.get('modality', ''),
                    'ReferringPhysicianName': '',
                    'PerformingPhysicianName': session.get('operator', '') or '',
                }

                study_info['NumberOfStudyRelatedSeries'] = len(scans)
                study_info['NumberOfStudyRelatedInstances'] = sum(
                    scan.get('instance_count', 0) for scan in scans
                )

                logger.info(f"   PatientID: {study_info['PatientID']}")
                logger.info(f"   PatientName: {study_info['PatientName']}")
                logger.info(f"   StudyInstanceUID: {study_info['StudyInstanceUID']}")
                logger.info(f"   StudyDescription: {study_info['StudyDescription']}")
                logger.info(f"   NumberOfStudyRelatedSeries: {study_info['NumberOfStudyRelatedSeries']}")
                logger.info(f"   NumberOfStudyRelatedInstances: {study_info['NumberOfStudyRelatedInstances']}")

                studies.append(study_info)
                logger.info(f"\n✅ Study added to results list")

            logger.info(f"Retrieved {len(studies)} studies from API")

            if studies:
                logger.info("=" * 80)
                logger.info("API QUERY RESPONSE:")
                logger.info("=" * 80)
                for idx, study in enumerate(studies, 1):
                    logger.info(f"\nStudy #{idx}:")
                    logger.info(f"  PatientID: {study.get('PatientID')}")
                    logger.info(f"  PatientName: {study.get('PatientName')}")
                    logger.info(f"  PatientBirthDate: {study.get('PatientBirthDate')}")
                    logger.info(f"  PatientSex: {study.get('PatientSex')}")
                    logger.info(f"  StudyInstanceUID: {study.get('StudyInstanceUID')}")
                    logger.info(f"  StudyID: {study.get('StudyID')}")
                    logger.info(f"  StudyDescription: {study.get('StudyDescription')}")
                    logger.info(f"  StudyDate: {study.get('StudyDate')}")
                    logger.info(f"  StudyTime: {study.get('StudyTime')}")
                    logger.info(f"  AccessionNumber: {study.get('AccessionNumber')}")
                    logger.info(f"  InstitutionName: {study.get('InstitutionName')}")
                    logger.info(f"  ModalitiesInStudy: {study.get('ModalitiesInStudy')}")
                    logger.info(f"  ReferringPhysicianName: {study.get('ReferringPhysicianName')}")
                    logger.info(f"  PerformingPhysicianName: {study.get('PerformingPhysicianName')}")
                    logger.info(f"  NumberOfStudyRelatedSeries: {study.get('NumberOfStudyRelatedSeries')}")
                    logger.info(f"  NumberOfStudyRelatedInstances: {study.get('NumberOfStudyRelatedInstances')}")
                logger.info("=" * 80)

            return studies

        except Exception as e:
            logger.error(f"Error querying studies from API: {e}", exc_info=True)
            return []

    def query_series_for_study(self, study_instance_uid: str) -> List[Dict[str, Any]]:
        """
        Query series for a specific study from API.

        Args:
            study_instance_uid: Study Instance UID

        Returns:
            List of series dictionaries
        """
        try:
            logger.info(f"Querying series for study {study_instance_uid} from API...")

            response = self.api_client.list_sessions()
            sessions = response.get('sessions', [])

            matching_session = None
            for session in sessions:
                if session.get('study_instance_uid') == study_instance_uid:
                    matching_session = session
                    break

            if not matching_session:
                logger.warning(f"No session found for study {study_instance_uid}")
                return []

            subject_id = matching_session.get('subject_id', '')
            session_id = matching_session.get('session_id', '')

            try:
                subject_response = self.api_client.get_subject(subject_id)
                subject_data = subject_response.get('subject', {})
                anonymous_id = subject_data.get('subject_identifier', subject_id)
                anonymous_name = subject_data.get('label', '')
            except Exception as e:
                logger.warning(f"Could not fetch subject {subject_id}: {e}")
                anonymous_id = subject_id
                anonymous_name = ''

            original = self.resolver.resolve_patient(
                anonymous_name=anonymous_name,
                anonymous_id=anonymous_id
            )

            if original:
                patient_id = original['original_id']
                patient_name = original['original_name']
                logger.debug(f"De-anonymized series: {anonymous_name} -> {patient_name}")
            else:
                patient_id = anonymous_id
                patient_name = anonymous_name
                logger.debug(f"No mapping found for series, using as-is: {anonymous_name}")

            logger.debug(f"Fetching scans for session_id: {session_id}")
            scans_response = self.api_client.list_scans(subject_id, session_id)
            scans = scans_response.get('scans', [])
            logger.info(f"Found {len(scans)} series from API")

            series_list = []
            for scan in scans:
                series_info = {
                    'PatientID': patient_id,
                    'PatientName': patient_name,
                    'StudyInstanceUID': study_instance_uid,
                    'SeriesInstanceUID': scan.get('series_instance_uid', ''),
                    'SeriesNumber': scan.get('scan_number', ''),
                    'SeriesDescription': scan.get('series_description', ''),
                    'Modality': scan.get('modality', ''),
                    'NumberOfSeriesRelatedInstances': scan.get('instance_count', 0),
                }

                series_list.append(series_info)

            return series_list

        except Exception as e:
            logger.error(f"Error querying series from API: {e}", exc_info=True)
            return []

    def query_images_for_series(
        self,
        study_instance_uid: str,
        series_instance_uid: str
    ) -> List[Dict[str, Any]]:
        """
        Query images for a specific series from API.

        Args:
            study_instance_uid: Study Instance UID
            series_instance_uid: Series Instance UID

        Returns:
            List of image dictionaries
        """
        try:
            logger.info(f"Querying images for series {series_instance_uid} from API...")

            response = self.api_client.list_sessions()
            sessions = response.get('sessions', [])

            matching_session = None
            for session in sessions:
                metadata = session.get('metadata', {})
                if metadata.get('study_instance_uid') == study_instance_uid:
                    matching_session = session
                    break

            if not matching_session:
                logger.warning(f"No session found for study {study_instance_uid}")
                return []

            scans = matching_session.get('scans', [])
            matching_scan = None
            for scan in scans:
                scan_metadata = scan.get('metadata', {})
                if scan_metadata.get('series_instance_uid') == series_instance_uid:
                    matching_scan = scan
                    break

            if not matching_scan:
                logger.warning(f"No scan found for series {series_instance_uid}")
                return []

            instances = matching_scan.get('instances', [])
            logger.info(f"Found {len(instances)} instances from API")

            images = []
            session_metadata = matching_session.get('metadata', {})
            scan_metadata = matching_scan.get('metadata', {})

            anonymous_id = matching_session.get('subject_id', '')
            anonymous_name = session_metadata.get('patient_name', '')

            original = self.resolver.resolve_patient(
                anonymous_name=anonymous_name,
                anonymous_id=anonymous_id
            )

            if original:
                patient_id = original['original_id']
                patient_name = original['original_name']
                logger.debug(f"De-anonymized images: {anonymous_name} → {patient_name}")
            else:
                patient_id = anonymous_id
                patient_name = anonymous_name
                logger.debug(f"No mapping found for images, using as-is: {anonymous_name}")

            for instance in instances:
                instance_metadata = instance.get('metadata', {})

                image_info = {
                    'PatientID': patient_id,
                    'PatientName': patient_name,
                    'StudyInstanceUID': study_instance_uid,
                    'SeriesInstanceUID': series_instance_uid,
                    'SOPInstanceUID': instance_metadata.get('sop_instance_uid', ''),
                    'SOPClassUID': instance_metadata.get('sop_class_uid', ''),
                    'InstanceNumber': instance_metadata.get('instance_number', ''),
                }

                images.append(image_info)

            return images

        except Exception as e:
            logger.error(f"Error querying images from API: {e}", exc_info=True)
            return []


def get_api_query_service() -> Optional[APIQueryService]:
    """
    Get API query service instance from DI container.

    Returns:
        APIQueryService instance or None
    """
    try:
        from receiver.containers import container

        api_client = container.ith_api_client()
        resolver = container.phi_resolver()

        return APIQueryService(api_client=api_client, resolver=resolver)

    except Exception as e:
        logger.warning(f"Could not create API query service: {e}")
        return None
