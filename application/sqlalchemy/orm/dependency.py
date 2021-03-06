# orm/dependency.py
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010 Michael Bayer mike_mp@zzzcomputing.com
#
# This module is part of SQLAlchemy and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php

"""Relationship dependencies.

"""

from sqlalchemy import sql, util
import sqlalchemy.exceptions as sa_exc
from sqlalchemy.orm import attributes, exc, sync, unitofwork, util as mapperutil
from sqlalchemy.orm.interfaces import ONETOMANY, MANYTOONE, MANYTOMANY

class DependencyProcessor(object):
    def __init__(self, prop):
        self.prop = prop
        self.cascade = prop.cascade
        self.mapper = prop.mapper
        self.parent = prop.parent
        self.secondary = prop.secondary
        self.direction = prop.direction
        self.post_update = prop.post_update
        self.passive_deletes = prop.passive_deletes
        self.passive_updates = prop.passive_updates
        self.enable_typechecks = prop.enable_typechecks
        self.key = prop.key
        if not self.prop.synchronize_pairs:
            raise sa_exc.ArgumentError(
                    "Can't build a DependencyProcessor for relationship %s. "
                    "No target attributes to populate between parent and "
                    "child are present" %
                     self.prop)
    
    @classmethod
    def from_relationship(cls, prop):
        return _direction_to_processor[prop.direction](prop)
        
    def hasparent(self, state):
        """return True if the given object instance has a parent,
        according to the ``InstrumentedAttribute`` handled by this 
        ``DependencyProcessor``.
        
        """
        return self.parent.class_manager.get_impl(self.key).hasparent(state)

    def per_property_preprocessors(self, uow):
        """establish actions and dependencies related to a flush.
        
        These actions will operate on all relevant states in
        the aggreagte.
        
        """
        uow.register_preprocessor(self, True)
        
        
    def per_property_flush_actions(self, uow):
        after_save = unitofwork.ProcessAll(uow, self, False, True)
        before_delete = unitofwork.ProcessAll(uow, self, True, True)

        parent_saves = unitofwork.SaveUpdateAll(
                                        uow, 
                                        self.parent.primary_base_mapper
                                        )
        child_saves = unitofwork.SaveUpdateAll(
                                        uow, 
                                        self.mapper.primary_base_mapper
                                        )

        parent_deletes = unitofwork.DeleteAll(
                                        uow, 
                                        self.parent.primary_base_mapper
                                        )
        child_deletes = unitofwork.DeleteAll(
                                        uow, 
                                        self.mapper.primary_base_mapper
                                        )
        
        self.per_property_dependencies(uow, 
                                        parent_saves, 
                                        child_saves, 
                                        parent_deletes, 
                                        child_deletes, 
                                        after_save, 
                                        before_delete)
        

    def per_state_flush_actions(self, uow, states, isdelete):
        """establish actions and dependencies related to a flush.
        
        These actions will operate on all relevant states 
        individually.    This occurs only if there are cycles
        in the 'aggregated' version of events.
        
        """

        # locate and disable the aggregate processors
        # for this dependency
        
        if isdelete:
            before_delete = unitofwork.ProcessAll(uow, self, True, True)
            before_delete.disabled = True
        else:
            after_save = unitofwork.ProcessAll(uow, self, False, True)
            after_save.disabled = True

        # check if the "child" side is part of the cycle
        
        parent_base_mapper = self.parent.primary_base_mapper
        child_base_mapper = self.mapper.primary_base_mapper
        child_saves = unitofwork.SaveUpdateAll(uow, child_base_mapper)
        child_deletes = unitofwork.DeleteAll(uow, child_base_mapper)
        
        if child_saves not in uow.cycles:
            # based on the current dependencies we use, the saves/
            # deletes should always be in the 'cycles' collection
            # together.   if this changes, we will have to break up
            # this method a bit more.
            assert child_deletes not in uow.cycles
            
            # child side is not part of the cycle, so we will link per-state
            # actions to the aggregate "saves", "deletes" actions
            child_actions = [
                (child_saves, False), (child_deletes, True)
            ]
            child_in_cycles = False
        else:
            child_in_cycles = True
        
        # check if the "parent" side is part of the cycle
        if not isdelete:
            parent_saves = unitofwork.SaveUpdateAll(
                                                uow, 
                                                self.parent.base_mapper)
            parent_deletes = before_delete = None
            if parent_saves in uow.cycles:
                parent_in_cycles = True
        else:
            parent_deletes = unitofwork.DeleteAll(
                                                uow, 
                                                self.parent.base_mapper)
            parent_saves = after_save = None
            if parent_deletes in uow.cycles:
                parent_in_cycles = True
        
        # now create actions /dependencies for each state.
        for state in states:
            # detect if there's anything changed or loaded
            # by a preprocessor on this state/attribute.  if not,
            # we should be able to skip it entirely.
            sum_ = uow.get_attribute_history(
                                            state, 
                                            self.key, 
                                            passive=True).sum()
            if not sum_:
                continue

            if isdelete:
                before_delete = unitofwork.ProcessState(uow, self, True, state)
                if parent_in_cycles:
                    parent_deletes = unitofwork.DeleteState(
                                                uow, 
                                                state, 
                                                parent_base_mapper)
            else:
                after_save = unitofwork.ProcessState(uow, self, False, state)
                if parent_in_cycles:
                    parent_saves = unitofwork.SaveUpdateState(
                                                uow, 
                                                state, 
                                                parent_base_mapper)
                
            if child_in_cycles:
                child_actions = []
                for child_state in sum_:
                    if child_state is None:
                        continue
                    if child_state not in uow.states:
                        child_action = (None, None)
                    else:
                        (deleted, listonly) = uow.states[child_state]
                        if deleted:
                            child_action = (
                                            unitofwork.DeleteState(
                                                        uow, child_state, 
                                                        child_base_mapper), 
                                            True)
                        else:
                            child_action = (
                                            unitofwork.SaveUpdateState(
                                                        uow, child_state, 
                                                        child_base_mapper), 
                                            False)
                    child_actions.append(child_action)
                    
            # establish dependencies between our possibly per-state
            # parent action and our possibly per-state child action.
            for (child_action, childisdelete) in child_actions:
                self.per_state_dependencies(uow, parent_saves, 
                                                parent_deletes, 
                                                child_action, 
                                                after_save, before_delete, 
                                                isdelete, childisdelete)
        
        
    def presort_deletes(self, uowcommit, states):
        return False
        
    def presort_saves(self, uowcommit, states):
        return False
        
    def process_deletes(self, uowcommit, states):
        pass
        
    def process_saves(self, uowcommit, states):
        pass

    def prop_has_changes(self, uowcommit, states, isdelete):
        for s in states:
            # TODO: add a high speed method 
            # to InstanceState which returns:  attribute
            # has a non-None value, or had one
            history = uowcommit.get_attribute_history(
                                            s, 
                                            self.key, 
                                            passive=True)
            if history and not history.empty():
                return True
        else:
            return False
        
    def _verify_canload(self, state):
        if state is not None and \
            not self.mapper._canload(state, allow_subtypes=not self.enable_typechecks):
            if self.mapper._canload(state, allow_subtypes=True):
                raise exc.FlushError(
                "Attempting to flush an item of type %s on collection '%s', "
                "which is not the expected type %s.  Configure mapper '%s' to "
                "load this subtype polymorphically, or set "
                "enable_typechecks=False to allow subtypes. "
                "Mismatched typeloading may cause bi-directional relationships "
                "(backrefs) to not function properly." % 
                (state.class_, self.prop, self.mapper.class_, self.mapper))
            else:
                raise exc.FlushError(
                "Attempting to flush an item of type %s on collection '%s', "
                "whose mapper does not inherit from that of %s." % 
                (state.class_, self.prop, self.mapper.class_))
            
    def _synchronize(self, state, child, associationrow,
                                            clearkeys, uowcommit):
        raise NotImplementedError()

    def _get_reversed_processed_set(self, uow):
        if not self.prop._reverse_property:
            return None

        process_key = tuple(sorted(
                        [self.key] + 
                        [p.key for p in self.prop._reverse_property]
                    ))
        return uow.memo(
                            ('reverse_key', process_key), 
                            set
                        )

    def _post_update(self, state, uowcommit, related, processed):
        if processed is not None and state in processed:
            return
        for x in related:
            if x is not None:
                uowcommit.issue_post_update(
                        state, 
                        [r for l, r in self.prop.synchronize_pairs]
                )
                if processed is not None:
                    processed.add(state)
                
                break
        
    def _pks_changed(self, uowcommit, state):
        raise NotImplementedError()

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, self.prop)

class OneToManyDP(DependencyProcessor):
    
    def per_property_dependencies(self, uow, parent_saves, 
                                                child_saves, 
                                                parent_deletes, 
                                                child_deletes, 
                                                after_save, 
                                                before_delete):
        if self.post_update:
            uow.dependencies.update([
                (child_saves, after_save),
                (parent_saves, after_save),
                (before_delete, parent_deletes),
                (before_delete, child_deletes),
            ])
        else:
            uow.dependencies.update([
                (parent_saves, after_save),
                (after_save, child_saves),
                (after_save, child_deletes),
    
                (child_saves, parent_deletes),
                (child_deletes, parent_deletes),

                (before_delete, child_saves),
                (before_delete, child_deletes),
            ])
            
    def per_state_dependencies(self, uow, 
                                    save_parent, 
                                    delete_parent, 
                                    child_action, 
                                    after_save, before_delete, 
                                    isdelete, childisdelete):
        
        if self.post_update:
            # TODO: this whole block is not covered
            # by any tests
            if not isdelete:
                if childisdelete:
                    uow.dependencies.update([
                        (save_parent, after_save),
                        (after_save, child_action)
                    ])
                else:
                    uow.dependencies.update([
                        (save_parent, after_save),
                        (child_action, after_save)
                    ])
            else:
                if childisdelete:
                    uow.dependencies.update([
                        (before_delete, delete_parent),
                        (before_delete, child_action)
                    ])
                else:
                    uow.dependencies.update([
                        (before_delete, delete_parent),
                        (child_action, before_delete)
                    ])
        elif not isdelete:
            uow.dependencies.update([
                (save_parent, after_save),
                (after_save, child_action),
                (save_parent, child_action)
            ])
        else:
            uow.dependencies.update([
                (before_delete, child_action),
                (child_action, delete_parent)
            ])
        
    def presort_deletes(self, uowcommit, states):
        # head object is being deleted, and we manage its list of 
        # child objects the child objects have to have their 
        # foreign key to the parent set to NULL
        should_null_fks = not self.cascade.delete and \
                            not self.passive_deletes == 'all'

        for state in states:
            history = uowcommit.get_attribute_history(
                                            state, 
                                            self.key, 
                                            passive=self.passive_deletes)
            if history:
                for child in history.deleted:
                    if child is not None and self.hasparent(child) is False:
                        if self.cascade.delete_orphan:
                            uowcommit.register_object(child, isdelete=True)
                        else:
                            uowcommit.register_object(child)
                
                if should_null_fks:
                    for child in history.unchanged:
                        if child is not None:
                            uowcommit.register_object(child)
        
            
    def presort_saves(self, uowcommit, states):
        children_added = uowcommit.memo(('children_added', self), set)
        
        for state in states:
            pks_changed = self._pks_changed(uowcommit, state)
            
            history = uowcommit.get_attribute_history(
                                            state, 
                                            self.key, 
                                            passive=not pks_changed 
                                                    or self.passive_updates)
            if history:
                for child in history.added:
                    if child is not None:
                        uowcommit.register_object(child, cancel_delete=True)

                children_added.update(history.added)

                for child in history.deleted:
                    if not self.cascade.delete_orphan:
                        uowcommit.register_object(child, isdelete=False)
                    elif self.hasparent(child) is False:
                        uowcommit.register_object(child, isdelete=True)
                        for c, m in self.mapper.cascade_iterator('delete', child):
                            uowcommit.register_object(
                                attributes.instance_state(c),
                                isdelete=True)

            if pks_changed:
                if history:
                    for child in history.unchanged:
                        if child is not None:
                            uowcommit.register_object(
                                        child, 
                                        False, 
                                        self.passive_updates)
        
    def process_deletes(self, uowcommit, states):
        # head object is being deleted, and we manage its list of 
        # child objects the child objects have to have their foreign 
        # key to the parent set to NULL this phase can be called 
        # safely for any cascade but is unnecessary if delete cascade
        # is on.
        if self.post_update:
            processed = self._get_reversed_processed_set(uowcommit)
        
        if self.post_update or not self.passive_deletes == 'all':
            children_added = uowcommit.memo(('children_added', self), set)

            for state in states:
                history = uowcommit.get_attribute_history(
                                            state, 
                                            self.key, 
                                            passive=self.passive_deletes)
                if history:
                    for child in history.deleted:
                        if child is not None and \
                            self.hasparent(child) is False:
                            self._synchronize(
                                            state, 
                                            child, 
                                            None, True, uowcommit)
                            if self.post_update and child:
                                    self._post_update(
                                            child, 
                                            uowcommit, 
                                            [state], processed)
                    if self.post_update or not self.cascade.delete:
                        for child in set(history.unchanged).\
                                            difference(children_added):
                            if child is not None:
                                self._synchronize(
                                            state, 
                                            child, 
                                            None, True, uowcommit)
                                if self.post_update and child:
                                    self._post_update(
                                            child, 
                                            uowcommit, 
                                            [state], processed)
                        # technically, we can even remove each child from the
                        # collection here too.  but this would be a somewhat 
                        # inconsistent behavior since it wouldn't happen if the old
                        # parent wasn't deleted but child was moved.
                            
    def process_saves(self, uowcommit, states):
        if self.post_update:
            processed = self._get_reversed_processed_set(uowcommit)
            
        for state in states:
            history = uowcommit.get_attribute_history(state, self.key, passive=True)
            if history:
                for child in history.added:
                    self._synchronize(state, child, None, False, uowcommit)
                    if child is not None and self.post_update:
                        self._post_update(
                                            child, 
                                            uowcommit, 
                                            [state],
                                            processed
                                            )

                for child in history.deleted:
                    if not self.cascade.delete_orphan and \
                        not self.hasparent(child):
                        self._synchronize(state, child, None, True, uowcommit)

                if self._pks_changed(uowcommit, state):
                    for child in history.unchanged:
                        self._synchronize(state, child, None, False, uowcommit)
        
    def _synchronize(self, state, child, associationrow, 
                                                clearkeys, uowcommit):
        source = state
        dest = child
        if dest is None or \
                (not self.post_update and uowcommit.is_deleted(dest)):
            return
        self._verify_canload(child)
        if clearkeys:
            sync.clear(dest, self.mapper, self.prop.synchronize_pairs)
        else:
            sync.populate(source, self.parent, dest, self.mapper, 
                                    self.prop.synchronize_pairs, uowcommit,
                                    self.passive_updates)

    def _pks_changed(self, uowcommit, state):
        return sync.source_modified(
                            uowcommit, 
                            state, 
                            self.parent, 
                            self.prop.synchronize_pairs)

class ManyToOneDP(DependencyProcessor):
    def __init__(self, prop):
        DependencyProcessor.__init__(self, prop)
        self.mapper._dependency_processors.append(DetectKeySwitch(prop))

    def per_property_dependencies(self, uow, 
                                        parent_saves, 
                                        child_saves, 
                                        parent_deletes, 
                                        child_deletes, 
                                        after_save, 
                                        before_delete):

        if self.post_update:
            uow.dependencies.update([
                (child_saves, after_save),
                (parent_saves, after_save),
                (before_delete, parent_deletes),
                (before_delete, child_deletes),
            ])
        else:
            uow.dependencies.update([
                (child_saves, after_save),
                (after_save, parent_saves),
                (parent_saves, child_deletes),
                (parent_deletes, child_deletes)
            ])

    def per_state_dependencies(self, uow, 
                                    save_parent, 
                                    delete_parent, 
                                    child_action, 
                                    after_save, before_delete, 
                                    isdelete, childisdelete):

        if self.post_update:
            if not isdelete:
                if childisdelete:
                    uow.dependencies.update([
                        (save_parent, after_save),
                        (after_save, child_action)
                    ])
                else:
                    uow.dependencies.update([
                        (save_parent, after_save),
                        (child_action, after_save)
                    ])
            else:
                uow.dependencies.update([
                    (before_delete, delete_parent),
                    (before_delete, child_action)
                ])
                    
        elif not isdelete:
            if not childisdelete:
                uow.dependencies.update([
                    (child_action, after_save),
                    (after_save, save_parent),
                ])
            else:
                uow.dependencies.update([
                    (after_save, save_parent),
                ])
                
        else:
            if childisdelete:
                uow.dependencies.update([
                    (delete_parent, child_action)
                ])

    def presort_deletes(self, uowcommit, states):
        if self.cascade.delete or self.cascade.delete_orphan:
            for state in states:
                history = uowcommit.get_attribute_history(
                                        state, 
                                        self.key, 
                                        passive=self.passive_deletes)
                if history:
                    if self.cascade.delete_orphan:
                        todelete = history.sum()
                    else:
                        todelete = history.non_deleted()
                    for child in todelete:
                        if child is None:
                            continue
                        uowcommit.register_object(child, isdelete=True)
                        for c, m in self.mapper.cascade_iterator(
                                                            'delete', child):
                            uowcommit.register_object(
                                attributes.instance_state(c), isdelete=True)
        
    def presort_saves(self, uowcommit, states):
        for state in states:
            uowcommit.register_object(state)
            if self.cascade.delete_orphan:
                history = uowcommit.get_attribute_history(
                                        state, 
                                        self.key, 
                                        passive=self.passive_deletes)
                if history:
                    ret = True
                    for child in history.deleted:
                        if self.hasparent(child) is False:
                            uowcommit.register_object(child, isdelete=True)
                            for c, m in self.mapper.cascade_iterator(
                                                            'delete', child):
                                uowcommit.register_object(
                                    attributes.instance_state(c),
                                    isdelete=True)

    def process_deletes(self, uowcommit, states):
        if self.post_update and \
                not self.cascade.delete_orphan and \
                not self.passive_deletes == 'all':
            
            processed = self._get_reversed_processed_set(uowcommit)
                
            # post_update means we have to update our 
            # row to not reference the child object
            # before we can DELETE the row
            for state in states:
                self._synchronize(state, None, None, True, uowcommit)
                if state and self.post_update:
                    history = uowcommit.get_attribute_history(
                                                state, 
                                                self.key, 
                                                passive=self.passive_deletes)
                    if history:
                        self._post_update(
                                            state, 
                                            uowcommit, 
                                            history.sum(), processed)

    def process_saves(self, uowcommit, states):
        if self.post_update:
            processed = self._get_reversed_processed_set(uowcommit)
            
        for state in states:
            history = uowcommit.get_attribute_history(state, self.key, passive=True)
            if history:
                for child in history.added:
                    self._synchronize(state, child, None, False, uowcommit)
                
                if self.post_update:
                    self._post_update(
                                        state, 
                                        uowcommit, history.sum(), processed)

    def _synchronize(self, state, child, associationrow, clearkeys, uowcommit):
        if state is None or (not self.post_update and uowcommit.is_deleted(state)):
            return

        if clearkeys or child is None:
            sync.clear(state, self.parent, self.prop.synchronize_pairs)
        else:
            self._verify_canload(child)
            sync.populate(child, self.mapper, state, 
                            self.parent, 
                            self.prop.synchronize_pairs, 
                            uowcommit,
                            self.passive_updates
                            )

class DetectKeySwitch(DependencyProcessor):
    """For many-to-one relationships with no one-to-many backref, 
    searches for parents through the unit of work when a primary
    key has changed and updates them.
    
    Theoretically, this approach could be expanded to support transparent
    deletion of objects referenced via many-to-one as well, although
    the current attribute system doesn't do enough bookkeeping for this
    to be efficient.
    
    """

    def per_property_preprocessors(self, uow):
        if self.prop._reverse_property:
            return
        
        uow.register_preprocessor(self, False)

    def per_property_flush_actions(self, uow):
        parent_saves = unitofwork.SaveUpdateAll(
                                        uow, 
                                        self.parent.base_mapper)
        after_save = unitofwork.ProcessAll(uow, self, False, False)
        uow.dependencies.update([
            (parent_saves, after_save)
        ])
        
    def per_state_flush_actions(self, uow, states, isdelete):
        pass
        
    def presort_deletes(self, uowcommit, states):
        pass

    def presort_saves(self, uow, states):
        if not self.passive_updates:
            # for non-passive updates, register in the preprocess stage
            # so that mapper save_obj() gets a hold of changes
            self._process_key_switches(states, uow)

    def prop_has_changes(self, uow, states, isdelete):
        if not isdelete and self.passive_updates:
            d = self._key_switchers(uow, states)
            return bool(d)
            
        return False
        
    def process_deletes(self, uowcommit, states):
        assert False

    def process_saves(self, uowcommit, states):
        # for passive updates, register objects in the process stage
        # so that we avoid ManyToOneDP's registering the object without
        # the listonly flag in its own preprocess stage (results in UPDATE)
        # statements being emitted
        assert self.passive_updates
        self._process_key_switches(states, uowcommit)
    
    def _key_switchers(self, uow, states):
        switched, notswitched = uow.memo(
                                        ('pk_switchers', self), 
                                        lambda: (set(), set())
                                    )
            
        allstates = switched.union(notswitched)
        for s in states:
            if s not in allstates:
                if self._pks_changed(uow, s):
                    switched.add(s)
                else:
                    notswitched.add(s)
        return switched
            
    def _process_key_switches(self, deplist, uowcommit):
        switchers = self._key_switchers(uowcommit, deplist)
        if switchers:
            # if primary key values have actually changed somewhere, perform
            # a linear search through the UOW in search of a parent.
            # note that this handler isn't used if the many-to-one 
            # relationship has a backref.
            for state in uowcommit.session.identity_map.all_states():
                if not issubclass(state.class_, self.parent.class_):
                    continue
                dict_ = state.dict
                related = dict_.get(self.key)
                if related is not None:
                    related_state = attributes.instance_state(dict_[self.key])
                    if related_state in switchers:
                        uowcommit.register_object(state, 
                                                    False, 
                                                    self.passive_updates)
                        sync.populate(
                                    related_state, 
                                    self.mapper, state, 
                                    self.parent, self.prop.synchronize_pairs, 
                                    uowcommit, self.passive_updates)

    def _pks_changed(self, uowcommit, state):
        return sync.source_modified(uowcommit, 
                                    state, 
                                    self.mapper, 
                                    self.prop.synchronize_pairs)


class ManyToManyDP(DependencyProcessor):
        
    def per_property_dependencies(self, uow, parent_saves, 
                                                child_saves, 
                                                parent_deletes, 
                                                child_deletes, 
                                                after_save, 
                                                before_delete):

        uow.dependencies.update([
            (parent_saves, after_save),
            (child_saves, after_save),
            (after_save, child_deletes),
            
            # a rowswitch on the parent from  deleted to saved 
            # can make this one occur, as the "save" may remove 
            # an element from the 
            # "deleted" list before we have a chance to
            # process its child rows
            (before_delete, parent_saves),
            
            (before_delete, parent_deletes),
            (before_delete, child_deletes),
            (before_delete, child_saves),
        ])

    def per_state_dependencies(self, uow, 
                                    save_parent, 
                                    delete_parent, 
                                    child_action, 
                                    after_save, before_delete, 
                                    isdelete, childisdelete):
        if not isdelete:
            if childisdelete:
                uow.dependencies.update([
                    (save_parent, after_save),
                    (after_save, child_action),
                ])
            else:
                uow.dependencies.update([
                    (save_parent, after_save),
                    (child_action, after_save),
                ])
        else:
            uow.dependencies.update([
                (before_delete, child_action),
                (before_delete, delete_parent)
            ])
        
    def presort_deletes(self, uowcommit, states):
        if not self.passive_deletes:
            for state in states:
                history = uowcommit.get_attribute_history(
                                        state, 
                                        self.key, 
                                        passive=self.passive_deletes)
        
    def presort_saves(self, uowcommit, states):
        for state in states:
            history = uowcommit.get_attribute_history(
                                    state, 
                                    self.key, 
                                    False)

        if not self.cascade.delete_orphan:
            return
            
        for state in states:
            history = uowcommit.get_attribute_history(
                                        state, 
                                        self.key, 
                                        passive=True)
            if history:
                for child in history.deleted:
                    if self.hasparent(child) is False:
                        uowcommit.register_object(child, isdelete=True)
                        for c, m in self.mapper.cascade_iterator(
                                                    'delete', 
                                                    child):
                            uowcommit.register_object(
                                attributes.instance_state(c), isdelete=True)
    
    def process_deletes(self, uowcommit, states):
        secondary_delete = []
        secondary_insert = []
        secondary_update = []
        
        processed = self._get_reversed_processed_set(uowcommit)
        
        for state in states:
            history = uowcommit.get_attribute_history(
                                    state, 
                                    self.key, 
                                    passive=self.passive_deletes)
            if history:
                for child in history.non_added():
                    if child is None or \
                        (processed is not None and (state, child) in processed) or \
                        not uowcommit.session._contains_state(child):
                        continue
                    associationrow = {}
                    self._synchronize(
                                        state, 
                                        child, 
                                        associationrow, 
                                        False, uowcommit)
                    secondary_delete.append(associationrow)
                
                if processed is not None:
                    processed.update((c, state) for c in history.non_added())
                
        self._run_crud(uowcommit, secondary_insert, 
                        secondary_update, secondary_delete)

    def process_saves(self, uowcommit, states):
        secondary_delete = []
        secondary_insert = []
        secondary_update = []

        processed = self._get_reversed_processed_set(uowcommit)
        
        for state in states:
            history = uowcommit.get_attribute_history(state, self.key)
            if history:
                for child in history.added:
                    if child is None or \
                            (processed is not None and (state, child) in processed):
                        continue
                    associationrow = {}
                    self._synchronize(state, 
                                        child, 
                                        associationrow, 
                                        False, uowcommit)
                    secondary_insert.append(associationrow)
                for child in history.deleted:
                    if child is None or \
                            (processed is not None and (state, child) in processed) or \
                            not uowcommit.session._contains_state(child):
                        continue
                    associationrow = {}
                    self._synchronize(state, 
                                        child, 
                                        associationrow, 
                                        False, uowcommit)
                    secondary_delete.append(associationrow)
                
                if processed is not None:
                    processed.update((c, state) for c in history.added + history.deleted)
                
            if not self.passive_updates and \
                    self._pks_changed(uowcommit, state):
                if not history:
                    history = uowcommit.get_attribute_history(
                                        state, 
                                        self.key, 
                                        passive=False)
                
                for child in history.unchanged:
                    associationrow = {}
                    sync.update(state, 
                                self.parent, 
                                associationrow, 
                                "old_", 
                                self.prop.synchronize_pairs)
                    sync.update(child, 
                                self.mapper, 
                                associationrow, 
                                "old_", 
                                self.prop.secondary_synchronize_pairs)

                    secondary_update.append(associationrow)
                    

        self._run_crud(uowcommit, secondary_insert, 
                        secondary_update, secondary_delete)
        
    def _run_crud(self, uowcommit, secondary_insert, 
                                        secondary_update, secondary_delete):
        connection = uowcommit.transaction.connection(self.mapper)
        
        if secondary_delete:
            associationrow = secondary_delete[0]
            statement = self.secondary.delete(sql.and_(*[
                                c == sql.bindparam(c.key, type_=c.type) 
                                for c in self.secondary.c 
                                if c.key in associationrow
                            ]))
            result = connection.execute(statement, secondary_delete)
            
            if result.supports_sane_multi_rowcount() and \
                        result.rowcount != len(secondary_delete):
                raise exc.ConcurrentModificationError(
                        "Deleted rowcount %d does not match number of "
                        "secondary table rows deleted from table '%s': %d" % 
                        (
                            result.rowcount, 
                            self.secondary.description, 
                            len(secondary_delete))
                        )

        if secondary_update:
            associationrow = secondary_update[0]
            statement = self.secondary.update(sql.and_(*[
                            c == sql.bindparam("old_" + c.key, type_=c.type) 
                            for c in self.secondary.c 
                            if c.key in associationrow
                        ]))
            result = connection.execute(statement, secondary_update)
            if result.supports_sane_multi_rowcount() and \
                        result.rowcount != len(secondary_update):
                raise exc.ConcurrentModificationError(
                            "Updated rowcount %d does not match number of "
                            "secondary table rows updated from table '%s': %d" % 
                            (
                                result.rowcount, 
                                self.secondary.description, 
                                len(secondary_update))
                            )

        if secondary_insert:
            statement = self.secondary.insert()
            connection.execute(statement, secondary_insert)
        
    def _synchronize(self, state, child, associationrow, clearkeys, uowcommit):
        if associationrow is None:
            return
        self._verify_canload(child)
        
        sync.populate_dict(state, self.parent, associationrow, 
                                        self.prop.synchronize_pairs)
        sync.populate_dict(child, self.mapper, associationrow,
                                        self.prop.secondary_synchronize_pairs)

    def _pks_changed(self, uowcommit, state):
        return sync.source_modified(
                            uowcommit, 
                            state, 
                            self.parent, 
                            self.prop.synchronize_pairs)

_direction_to_processor = {
    ONETOMANY : OneToManyDP,
    MANYTOONE: ManyToOneDP,
    MANYTOMANY : ManyToManyDP,
}

