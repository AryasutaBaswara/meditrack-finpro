BEGIN;

INSERT INTO storage.buckets (id, name, public)
VALUES (
	'prescription-files',
	'prescription-files',
	FALSE
)
ON CONFLICT (id) DO UPDATE
SET name = EXCLUDED.name,
	public = EXCLUDED.public;

INSERT INTO roles (id, name, description)
VALUES
	('10000000-0000-0000-0000-000000000001', 'admin', 'System administrator'),
	('10000000-0000-0000-0000-000000000002', 'doctor', 'Medical doctor'),
	('10000000-0000-0000-0000-000000000003', 'pharmacist', 'Dispensing pharmacist'),
	('10000000-0000-0000-0000-000000000004', 'patient', 'Registered patient')
ON CONFLICT (name) DO UPDATE
SET description = EXCLUDED.description;

INSERT INTO clinics (id, name, address, phone, email)
VALUES (
	'20000000-0000-0000-0000-000000000001',
	'MediTrack Clinic Jakarta',
	'Jl. Kesehatan No. 10, Jakarta',
	'+62-21-555-0100',
	'clinic@meditrack.local'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO users (id, keycloak_sub, email, is_active)
VALUES
	(
		'30000000-0000-0000-0000-000000000001',
		'f00e1e8c-5530-414b-abfc-eb71750575b4',
		'admin@meditrack.local',
		TRUE
	),
	(
		'30000000-0000-0000-0000-000000000002',
		'6af15c51-f038-4b04-8e98-180c2422fe7f',
		'doctor@meditrack.local',
		TRUE
	),
	(
		'30000000-0000-0000-0000-000000000003',
		'd21b432a-a140-4a40-b1df-656cfd0670cc',
		'pharmacist@meditrack.local',
		TRUE
	),
	(
		'30000000-0000-0000-0000-000000000004',
		'43e1b72e-2f4e-470c-95f2-8efb58ce6e11',
		'patient@meditrack.local',
		TRUE
	)
ON CONFLICT (keycloak_sub) DO UPDATE
SET email = EXCLUDED.email,
	is_active = EXCLUDED.is_active,
	deleted_at = NULL;

INSERT INTO profiles (id, user_id, full_name, nik, phone, address, date_of_birth)
VALUES
	(
		'40000000-0000-0000-0000-000000000001',
		'30000000-0000-0000-0000-000000000001',
		'Local Admin',
		'3173000000000001',
		'+62-811-0000-0001',
		'Jakarta',
		'1990-01-01'
	),
	(
		'40000000-0000-0000-0000-000000000002',
		'30000000-0000-0000-0000-000000000002',
		'Dr. Local Doctor',
		'3173000000000002',
		'+62-811-0000-0002',
		'Jakarta',
		'1988-05-12'
	),
	(
		'40000000-0000-0000-0000-000000000003',
		'30000000-0000-0000-0000-000000000003',
		'Local Pharmacist',
		'3173000000000003',
		'+62-811-0000-0003',
		'Jakarta',
		'1992-09-03'
	),
	(
		'40000000-0000-0000-0000-000000000004',
		'30000000-0000-0000-0000-000000000004',
		'Local Patient',
		'3173000000000004',
		'+62-811-0000-0004',
		'Bandung',
		'1995-11-21'
	)
ON CONFLICT (user_id) DO UPDATE
SET full_name = EXCLUDED.full_name,
	nik = EXCLUDED.nik,
	phone = EXCLUDED.phone,
	address = EXCLUDED.address,
	date_of_birth = EXCLUDED.date_of_birth;

INSERT INTO user_roles (id, user_id, role_id)
VALUES
	(
		'50000000-0000-0000-0000-000000000001',
		'30000000-0000-0000-0000-000000000001',
		'10000000-0000-0000-0000-000000000001'
	),
	(
		'50000000-0000-0000-0000-000000000002',
		'30000000-0000-0000-0000-000000000002',
		'10000000-0000-0000-0000-000000000002'
	),
	(
		'50000000-0000-0000-0000-000000000003',
		'30000000-0000-0000-0000-000000000003',
		'10000000-0000-0000-0000-000000000003'
	),
	(
		'50000000-0000-0000-0000-000000000004',
		'30000000-0000-0000-0000-000000000004',
		'10000000-0000-0000-0000-000000000004'
	)
ON CONFLICT (user_id, role_id) DO NOTHING;

INSERT INTO doctors (id, user_id, clinic_id, sip_number, specialization)
VALUES (
	'60000000-0000-0000-0000-000000000001',
	'30000000-0000-0000-0000-000000000002',
	'20000000-0000-0000-0000-000000000001',
	'SIP-LOCAL-DOCTOR-001',
	'General Medicine'
)
ON CONFLICT (user_id) DO UPDATE
SET clinic_id = EXCLUDED.clinic_id,
	sip_number = EXCLUDED.sip_number,
	specialization = EXCLUDED.specialization,
	deleted_at = NULL;

INSERT INTO patients (id, user_id, blood_type, allergies, emergency_contact)
VALUES (
	'70000000-0000-0000-0000-000000000001',
	'30000000-0000-0000-0000-000000000004',
	'O+',
	'No known drug allergies',
	'Family Contact +62-811-9999-0001'
)
ON CONFLICT (user_id) DO UPDATE
SET blood_type = EXCLUDED.blood_type,
	allergies = EXCLUDED.allergies,
	emergency_contact = EXCLUDED.emergency_contact,
	deleted_at = NULL;

INSERT INTO drugs (id, name, generic_name, category, description, stock, price, unit, manufacturer)
VALUES
	(
		'80000000-0000-0000-0000-000000000001',
		'Paracetamol 500mg',
		'Paracetamol',
		'Analgesic',
		'Pain relief and fever reducer for smoke testing.',
		200,
		5000.00,
		'tablet',
		'MediTrack Pharma'
	),
	(
		'80000000-0000-0000-0000-000000000002',
		'Amoxicillin 500mg',
		'Amoxicillin',
		'Antibiotic',
		'Broad-spectrum antibiotic for smoke testing.',
		120,
		12000.00,
		'capsule',
		'MediTrack Pharma'
	),
	(
		'80000000-0000-0000-0000-000000000003',
		'Ibuprofen 400mg',
		'Ibuprofen',
		'NSAID',
		'Anti-inflammatory drug for smoke testing.',
		90,
		9000.00,
		'tablet',
		'MediTrack Pharma'
	)
ON CONFLICT (id) DO UPDATE
SET name = EXCLUDED.name,
	generic_name = EXCLUDED.generic_name,
	category = EXCLUDED.category,
	description = EXCLUDED.description,
	stock = EXCLUDED.stock,
	price = EXCLUDED.price,
	unit = EXCLUDED.unit,
	manufacturer = EXCLUDED.manufacturer,
	deleted_at = NULL;

COMMIT;
