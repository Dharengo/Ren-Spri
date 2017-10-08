init python:
    
    from numbers import Number
    from xml.etree import ElementTree
    from os import path
    
    config.automatic_images_strip += 'spriter', 'Spriter' #Prevents spriter images from being unnecessarily loaded
    
    output = "" #for debugging purposes
    
    #Some commonly used expressions
    _id = lambda x: int(x.get("id"))
    _all_ids = lambda a: (_id(x) for x in a)
    
    def _append_child(parent, child):
        if not hasattr(parent, "_children"):
            parent._children = []
        parent._children.append(child)
    
    def _spriter_import():
        for file in renpy.list_files():
            if '.scml' in file and 'autosave' not in file and renpy.loadable(file):
                rootdir = path.dirname(file)
                with renpy.file(file) as scml:
                    tree = ElementTree.parse(scml)
                folders = tree.findall("folder")
                images = [None] * len(folders)
                for folder in folders:
                    ims = folder.findall("file")
                    sl = images[_id(folder)] = [None] * len(ims)
                    for image in ims:
                        sl[_id(image)] = renpy.displayable(path.join(rootdir, image.get("name")))
                for entity in tree.findall("entity"):
                    tag = entity.get("name") + " "
                    for animation in entity.findall("animation"):
                        renpy.image(tag + animation.get("name"), SpriterAnimation(animation, images))
                    
    class SpriterAnimation(renpy.Displayable):
        def __init__(self, tree, images, **kwargs):
            super(type(self), self).__init__(**kwargs)
            if isinstance(tree, ElementTree.Element) and tree.tag == "animation":
                self._length = int(tree.get("length"))
                self._interval = int(tree.get("interval"))
                bones = tree.findall("./mainline/key/bone_ref")
                objs = tree.findall("./mainline/key/object_ref")
                parents = [None] * (max(_all_ids(bones)) + 1)
                ims = [None] * (max(_all_ids(objs)) + 1)
                global output
                output = parents
                for ref in bones:
                    id = _id(ref)
                    if not parents[id]:
                        parents[id] = self._Animator(self, tree, ref, parents, images)
                for ref in objs:
                    id = _id(ref)
                    if not ims[id]:
                        ims[id] = self._Animator(self, tree, ref, parents, images)
                ###TODO: INCORPORATE A DICTIONARY FOR BONES###
  
        class _Animator():
            def __init__(self, root, tree, ref, parents, images, **kwargs):
                super(type(self), self).__init__(**kwargs)
                if isinstance(tree, ElementTree.Element) and tree.tag == "animation":
                    p = ref.get("parent")
                    if p:
                        _append_child(parents[int(p)], self)
                    else:
                        _append_child(root, self)
                        
    class SpriterObject(renpy.Displayable):
        """
        A Spriter Entity consists of several SpriterObjects, be it the root Entity,
        Bones, or Parts. All of these can have children postioned relative to their
        parents. Base class, do not instantiate.
        """        
        def __init__(self, children=[], **kwargs):
            super(SpriterObject, self).__init__(**kwargs)
            
            #All the direct children of this object, may be other Bones or Parts
            self._children = children
            
        def render(self, width, height, st, at):
            """Generic render, simply renders its children"""
            render = renpy.Render(width, height)
            for child in _children:
                render.place(child)
            return render
            
        def visit(self):
            return self._children
         
    class Timeline():
        """Container for keyframes for a single child"""
        def __init__(self, keys, object, anim_length):
            #The list of keys, gets sorted by time
            keys.sort(key=lambda x: x.time)
            self._keys = keys
            self._length = len(keys)
            self._anim_length = anim_length
            
            #A transform containing a Spriter Object as a child
            self._obj = object
            
            #The most recent keyframe
            self._prev = 0
            self._speed = 100
            
        def _transform_callback(self):
            def c(trans, st, at):
                time = st * 100 % self._anim_length
                #global output
                #output = str(time)
                prev = self._prev
                next = prev + 1
                if next >= self._length:
                    next = 0
                while next != 0 and time > self._keys[next].time or time < self._keys[prev].time:
                    prev = self._prev = next
                    next += 1
                    if next >= self._length:
                        next = 0
                prev = self._keys[prev]
                props = prev._props
                if prev.time != time:
                    next = self._keys[next]
                    ptime, ntime = prev.time, next.time
                    prev, next = prev._props, next._props
                    fraction = float(time - ptime) / float(ntime - ptime)
                    props = {}
                    for k, prop in prev.items():
                        if k in next:
                            if prop != next[k]:
                                if isinstance(prop, Number):
                                    prop += (next[k] - prop) * fraction
                        props[k] = prop
                for name, val in props.items():
                    if name == 'image':
                        trans.set_child(val)
                    else:
                        setattr(trans, name, val)
                return 0
            return c
        
        def _transform(self):
            return Transform(self._obj, self._transform_callback())
                            
    class Key():
        """
        Contains positioning and transformation data for every frame
        of a Spriter animation.
        """
        
        def __init__(self, time, properties):
            #The frame that this key applies to
            self.time = time
            
            #A dict of properties to iterate through
            self._props = properties
            
    class Animation():
        """All the animation data."""
        def __init__(self, length, mainline, timelines):
            #All the keys of the animation, in a list
            self._mainline = mainline
            
            self._timelines = timelines
            
            #Length in frames
            self._length = length
            
        def _render(self, width, height, st, at):
            """Renders child Bones or Parts"""
            tr = renpy.render(self._timelines[0]._transform(), width, height, st, at)
            r = renpy.Render(*tr.get_size())
            r.blit(tr, (0, 0))
            return r
            
    class Entity(SpriterObject):
        """
        The root-level SpriterObject. 
        Determines the total size of the thing, as well as the framerate.
        """
        def __init__(self, animations=[], speed=100, **kwargs):
            super(Entity, self).__init__(**kwargs)
            
            #A dict of all animations
            self._animations = animations
            for name in 'idle', 'Idle', 'default', 'Default', 'normal', 'Normal':
                if name in animations:
                    self.animate(name)
                    break
            
            #Animation speed in frames per second, this is different from the refresh rate
            self._speed = speed
            
        def animate(self, name):
            """Starts an animation."""
            #set the animation's start time
            self._start = 0
            self._current_anim = self._animations[name]
            
        def render(self, width, height, st, at):
            return self._current_anim._render(width, height, st, at)
            
    _spriter_import()