"""Local regression tests. Run: python -m unittest discover -s tests -v"""
import io
import tempfile
import unittest
import app as finance
from storage import LocalStore
from openpyxl import load_workbook

class FinanceFlows(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_store = finance.store
        finance.store = LocalStore()
        finance.store.path = self.tmp.name + '/funds.json'
        finance.app.config['TESTING'] = True
        self.client = finance.app.test_client()
    def tearDown(self):
        finance.store = self.old_store
        self.tmp.cleanup()
    def sign_in(self):
        self.client.post('/login', data={'username': finance.OWNER_USER, 'password': finance.OWNER_PASS})
    def test_owner_only_access(self):
        self.assertEqual(self.client.get('/api/funds').status_code, 401)
        self.assertEqual(self.client.get('/').status_code, 302)
        self.sign_in()
        self.assertEqual(self.client.get('/api/funds').status_code, 200)
        self.client.get('/logout')
        self.assertEqual(self.client.get('/api/funds').status_code, 401)
    def test_fund_save_reads_back(self):
        self.sign_in()
        fid = self.client.post('/api/funds', json={'name': 'Class Fund'}).json['id']
        rows = [{'date':'2026-10-20','description':'Contribution','category':'Class','type':'income','amount':'100','tax':'10'}]
        self.assertEqual(self.client.put('/api/funds/'+fid,json={'rows':rows}).status_code,200)
        self.assertEqual(self.client.get('/api/funds/'+fid).json['rows'],rows)
    def test_spreadsheet_tax_round_trip(self):
        self.sign_in()
        rows = [{'date':'2026-10-20','description':'Contribution','category':'Class','type':'income','amount':'100','tax':'10'}]
        result = self.client.post('/ledger/export',json={'rows':rows})
        self.assertEqual(result.status_code,200)
        wb=load_workbook(io.BytesIO(result.data))
        self.assertEqual(wb['Ledger']['F2'].value,.1)
        self.assertEqual(wb['Ledger']['H2'].value,'=E2+G2')
        imported=self.client.post('/ledger/import',data={'file':(io.BytesIO(result.data),'ledger.xlsx')})
        self.assertEqual(imported.status_code,200)
        self.assertEqual(imported.json['rows'][0]['tax'],10)
        self.assertEqual(imported.json['rows'][0]['amount'],100)
    def test_file_audit_export(self):
        self.sign_in()
        csv=b'Date,Amount,Description\n2026-10-20,100,Contribution\n2026-10-20,100,Contribution\n'
        result=self.client.post('/audit',data={'file':(io.BytesIO(csv),'audit.csv')})
        self.assertEqual(result.status_code,200)
        self.assertIn(b'Duplicate',result.data)
        rid=list(finance.REPORTS)[-1]
        report=self.client.get('/export/'+rid)
        self.assertEqual(report.status_code,200)
        wb=load_workbook(io.BytesIO(report.data))
        self.assertEqual(len(wb.sheetnames),5)

if __name__=='__main__':
    unittest.main()
