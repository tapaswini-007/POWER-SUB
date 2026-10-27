// Safe Blob Download Helper

/**
 * Triggers an in-browser download of a binary Blob with automatic object URL cleanup.
 * @param {Blob} blob
 * @param {string} reportType - e.g. 'summary_pdf', 'anomalies_csv'
 * @param {string} datasetId - UUID of the dataset
 * @param {string} extension - 'pdf' or 'csv'
 * @param {string} [expectedMime='']
 */
export function triggerBlobDownload(blob, reportType, datasetId, extension, expectedMime = '') {
  if (!(blob instanceof Blob)) {
    throw new Error('Invalid download data: expected a binary Blob.');
  }

  // Verify Content-Type if specified
  if (expectedMime && blob.type && !blob.type.includes(expectedMime)) {
    throw new Error(`Unexpected file format: expected ${expectedMime}, but received ${blob.type}.`);
  }

  // Generate safe filename: power_sub_<report-type>_<first8-of-datasetId>_<YYYYMMDD>.<ext>
  const shortId = (datasetId || 'data').replace(/[^a-zA-Z0-9]/g, '').substring(0, 8) || 'export';
  const now = new Date();
  const yyyy = now.getFullYear();
  const mm = String(now.getMonth() + 1).padStart(2, '0');
  const dd = String(now.getDate()).padStart(2, '0');
  const cleanType = (reportType || 'report').replace(/[^a-zA-Z0-9_-]/g, '');
  const cleanExt = (extension || 'bin').replace(/[^a-zA-Z0-9]/g, '');

  const safeFilename = `power_sub_${cleanType}_${shortId}_${yyyy}${mm}${dd}.${cleanExt}`;

  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = objectUrl;
  anchor.download = safeFilename;
  anchor.style.display = 'none';

  document.body.appendChild(anchor);
  try {
    anchor.click();
  } finally {
    document.body.removeChild(anchor);
    // Revoke object URL immediately after click to release memory
    setTimeout(() => {
      URL.revokeObjectURL(objectUrl);
    }, 1000);
  }
}
