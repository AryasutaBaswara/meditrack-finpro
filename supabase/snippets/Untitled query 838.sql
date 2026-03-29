SELECT proname, prosecdef FROM pg_proc
  WHERE proname IN (
   'get_prescription_detail',
   'get_my_prescriptions',
   'get_pharmacist_queue',
   'get_patient_files'
 );