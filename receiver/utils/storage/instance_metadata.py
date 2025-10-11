"""
Instance Metadata XML Handler
Manages instance metadata in XML format for efficient storage and retrieval.
Avoids database bloat by storing instance metadata in XML files per series.
"""
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Optional
import threading
from datetime import datetime


class InstanceMetadataHandler:
    """
    Handles reading and writing instance metadata to XML files.
    Thread-safe operations for concurrent access.
    """

    def __init__(self):
        self._lock = threading.Lock()

    def add_instance(
        self,
        xml_path: Path,
        sop_instance_uid: str,
        instance_number: int,
        file_name: str,
        file_size: int,
        transfer_syntax_uid: str = ''
    ) -> bool:
        """
        Add instance metadata to XML file.

        Args:
            xml_path: Path to instances.xml file
            sop_instance_uid: SOP Instance UID
            instance_number: Instance number
            file_name: DICOM file name
            file_size: File size in bytes
            transfer_syntax_uid: Transfer syntax UID

        Returns:
            bool: True if successful
        """
        with self._lock:
            try:
                if xml_path.exists():
                    tree = ET.parse(xml_path)
                    root = tree.getroot()
                else:
                    root = ET.Element('instances')
                    tree = ET.ElementTree(root)

                for instance in root.findall('instance'):
                    if instance.find('sop_instance_uid').text == sop_instance_uid:
                        instance.find('file_name').text = file_name
                        instance.find('file_size').text = str(file_size)
                        instance.find('transfer_syntax_uid').text = transfer_syntax_uid
                        instance.find('updated_at').text = datetime.now().isoformat()
                        self._write_xml(tree, xml_path)
                        return True

                instance_elem = ET.SubElement(root, 'instance')
                ET.SubElement(instance_elem, 'sop_instance_uid').text = sop_instance_uid
                ET.SubElement(instance_elem, 'instance_number').text = str(instance_number)
                ET.SubElement(instance_elem, 'file_name').text = file_name
                ET.SubElement(instance_elem, 'file_size').text = str(file_size)
                ET.SubElement(instance_elem, 'transfer_syntax_uid').text = transfer_syntax_uid
                ET.SubElement(instance_elem, 'created_at').text = datetime.now().isoformat()
                ET.SubElement(instance_elem, 'updated_at').text = datetime.now().isoformat()

                self._write_xml(tree, xml_path)
                return True

            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Error adding instance to XML: {e}", exc_info=True)
                return False

    def get_instances(self, xml_path: Path) -> List[Dict]:
        """
        Get all instances from XML file.

        Args:
            xml_path: Path to instances.xml file

        Returns:
            List of instance dictionaries
        """
        with self._lock:
            try:
                if not xml_path.exists():
                    return []

                tree = ET.parse(xml_path)
                root = tree.getroot()

                instances = []
                for instance in root.findall('instance'):
                    instances.append({
                        'sop_instance_uid': instance.find('sop_instance_uid').text,
                        'instance_number': int(instance.find('instance_number').text),
                        'file_name': instance.find('file_name').text,
                        'file_size': int(instance.find('file_size').text),
                        'transfer_syntax_uid': instance.find('transfer_syntax_uid').text or '',
                        'created_at': instance.find('created_at').text,
                        'updated_at': instance.find('updated_at').text,
                    })

                return instances

            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Error reading instances from XML: {e}", exc_info=True)
                return []

    def get_all_instances(self, xml_path: Path) -> List[Dict]:
        """
        Alias for get_instances for consistency with old project.

        Args:
            xml_path: Path to instances.xml file

        Returns:
            List of instance dictionaries
        """
        return self.get_instances(xml_path)

    def get_instance(self, xml_path: Path, sop_instance_uid: str) -> Optional[Dict]:
        """
        Get specific instance by SOP Instance UID.

        Args:
            xml_path: Path to instances.xml file
            sop_instance_uid: SOP Instance UID to find

        Returns:
            Instance dictionary or None
        """
        instances = self.get_instances(xml_path)
        for instance in instances:
            if instance['sop_instance_uid'] == sop_instance_uid:
                return instance
        return None

    def get_instance_count(self, xml_path: Path) -> int:
        """
        Get count of instances in XML file.

        Args:
            xml_path: Path to instances.xml file

        Returns:
            Number of instances
        """
        try:
            if not xml_path.exists():
                return 0

            tree = ET.parse(xml_path)
            root = tree.getroot()
            return len(root.findall('instance'))

        except Exception:
            return 0

    def remove_instance(self, xml_path: Path, sop_instance_uid: str) -> bool:
        """
        Remove instance from XML file.

        Args:
            xml_path: Path to instances.xml file
            sop_instance_uid: SOP Instance UID to remove

        Returns:
            bool: True if successful
        """
        with self._lock:
            try:
                if not xml_path.exists():
                    return False

                tree = ET.parse(xml_path)
                root = tree.getroot()

                for instance in root.findall('instance'):
                    if instance.find('sop_instance_uid').text == sop_instance_uid:
                        root.remove(instance)
                        self._write_xml(tree, xml_path)
                        return True

                return False

            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Error removing instance from XML: {e}", exc_info=True)
                return False

    def _write_xml(self, tree: ET.ElementTree, xml_path: Path):
        """
        Write XML tree to file with pretty formatting.

        Args:
            tree: ElementTree object
            xml_path: Path to write to
        """
        xml_path.parent.mkdir(parents=True, exist_ok=True)

        self._indent(tree.getroot())

        tree.write(xml_path, encoding='utf-8', xml_declaration=True)

    def _indent(self, elem, level=0):
        """
        Add indentation to XML for readability.

        Args:
            elem: XML element
            level: Indentation level
        """
        indent = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = indent + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = indent
            for child in elem:
                self._indent(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = indent
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = indent
