"""Authored proof-search kernel regressions; excluded from model PoC scoring."""
import tempfile
import unittest
from pathlib import Path
from verislop import leanbridge
from verislop import prove

PROFILE={'symbols':{'prefix':{'lean_decl':'Search.prefix'}},'predicates':{},'enums':{'E':{'lean_constructors':['Search.E.zero','Search.E.one']}},'records':{
 'R':{'lean_constructor':'Search.R.mk','fields':[{'name':'values','sort':{'list':'Int'}},{'name':'minimum','sort':'Int'},{'name':'text','sort':'String'}]},
 'Outer':{'lean_constructor':'Search.Outer.mk','fields':[{'name':'row','sort':{'record':'R'}},{'name':'enabled','sort':'Bool'}]}}}
def exists(sort,body=None): return {'tag':'exists','sort':sort,'body':body or {'tag':'true'}}
def statement(name,formula): return {'role':'guarantee','lean_symbol':'Search.'+name,'representation':'contract_dsl','formula_package':{'formula':formula}}

class PortfolioTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory(); cls.tc=leanbridge.resolve_toolchain();cls.root=Path(cls.tmp.name)
 @classmethod
 def tearDownClass(cls): cls.tmp.cleanup()
 def compile(self,source): return leanbridge.compile_module(self.tc, source.encode(),self.root/'compile')
 def test_typed_defaults_and_quote_lookup_close_actual_lean_goals(self):
  goals=[('nat','∃ x : Nat, True',exists('Nat')),('signed','∃ x : Int, x < 0',exists('Int')),('bool','∃ x : Bool, x = true',exists('Bool')),('unit','∃ x : Unit, True',exists('Unit')),('string','∃ x : String, x = "x"',exists('String')),('list','∃ x : List Int, True',exists({'list':'Int'})),('row','∃ x : R, x.minimum < 0',exists({'record':'R'})),('outer','∃ x : Outer, True',exists({'record':'Outer'})),('enum','∃ x : E, x = E.one',exists({'enum':'E'})),('result','∃ x : Except Int String, True',exists({'result':{'error':'Int','ok':'String'}})),('«forall»','∀ n : Nat, «prefix» n = n+1',{'tag':'true'}),('«exists»','∃ n : Nat, True',exists('Nat'))]
  source='import Std\nnamespace Search\ninductive E where | zero | one deriving DecidableEq\nstructure R where\n  values : List Int\n  minimum : Int\n  text : String\nstructure Outer where\n  row : R\n  enabled : Bool\ndef «prefix» (n : Nat) := n+1\n'
  statements={}
  for name,text,formula in goals:
   source+=f'theorem {name} : {text} := by sorry\n'; statements[name]=statement(name.strip('«»'),formula)
  source+='end Search\n'; candidate=prove.apply_portfolio(source,statements,PROFILE)
  comp=self.compile(candidate);self.assertTrue(comp.ok,comp.errors);self.assertEqual([],comp.sorry_positions)
 def test_nested_conjunction_has_branch_specific_sorts(self):
  formula={'tag':'and','left':exists('String'),'right':{'tag':'and','left':exists({'record':'R'}),'right':exists('Int')}}
  tactic=prove.portfolio_tactic(statement('nested',formula),[],PROFILE)
  source='import Std\nnamespace Search\nstructure R where\n  values : List Int\n  minimum : Int\n  text : String\ntheorem nested : (∃ x : String, True) ∧ ((∃ r : R, True) ∧ (∃ x : Int, x < 0)) := by '+tactic+'\nend Search\n'
  comp=self.compile(source);self.assertTrue(comp.ok,comp.errors);self.assertEqual([],comp.sorry_positions)
 def test_false_existential_stays_unresolved(self):
  tactic=prove.portfolio_tactic(statement('falsehood',exists('Int',{'tag':'false'})),[],PROFILE)
  comp=self.compile('import Std\ntheorem falsehood : ∃ x : Int, False := by '+tactic+'\n')
  self.assertTrue(comp.ok,comp.errors);self.assertGreater(len(comp.sorry_positions),0)
 def test_recursive_or_huge_carrier_search_is_bounded(self):
  recursive={'records':{'R':{'lean_constructor':'Search.R.mk','fields':[{'sort':{'record':'R'}}]}},'enums':{}}
  tactic=prove.portfolio_tactic(statement('loop',exists({'record':'R'})),[],recursive)
  self.assertLess(len(tactic),200);self.assertIn('sorry',tactic)
  formula={'tag':'true'}
  for _ in range(5): formula=exists('Nat',formula)
  self.assertEqual('sorry',prove.portfolio_tactic(statement('too_many',formula),[],PROFILE))

if __name__=='__main__': unittest.main()
