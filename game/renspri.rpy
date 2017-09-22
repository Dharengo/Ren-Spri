init python:
    
    from numbers import Number
    import xml.etree.ElementTree as Xml
    
    class SpriterObject(renpy.Displayable):
        """
        A Spriter Entity consists of several SpriterObjects, be it the root Entity,
        Bones, or Parts. All of these can have children postioned relative to their
        parents. Base class, do not instantiate.
        """
        @classmethod
        def transform(cls, children, *args, **kwargs):
            """Factory method that returns a transform containing an instance"""
            return Transform(cls(children, *args, **kwargs))
        
        def __init__(self, children, *args, **kwargs):
            super().__init__(*args, **kwargs)
            
            #All the direct children of this object, may be other Bones or Parts
            self._children = children
            
        def render(self, width, height, st, at):
            """Generic render, simply renders its children"""
            render = renpy.Render(0, 0)
            for child in _children:
                render.place(child)
            return render
            
        def visit(self):
            return self.children
         
    class Timeline():
        """Container for keyframes for a single child"""
        def __init__(self, keys, transform):
            #The list of keys, gets sorted by time
            keys.sort(lambda x: x.time)
            self._keys = keys
            self._length = len(keys)
            
            #A transform containing a Spriter Object as a child
            self._transform = transform
            
            #The most recent keyframe
            self._prev = 0
            
        def set_key(self, time):
            """Sets a key to attached transform, either one of the keyframe keys, or an interpolated one."""
            #Make sure we're in the proper time window
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
            props = prev.props
            if prev.time != time:
                next = self._keys[next]
                ptime, ntime = prev.time, next.time
                prev, next = prev.properties, next.properties
                fraction = float(time - ptime) / float(ntime - ptime)
                props = {}
                for k in prev:
                    prop = prev[k]
                    if k in next:
                        if prop != next[k]:
                            if isinstance(prop, Number):
                                prop += (next[k] - prop) * fraction
                    props[k] = prop
            t = self._transform
            if 'x' in props:
                t.xcenter = props['x']
            if 'y' in props:
                t.ycenter = props['y']
            if 'angle' in props:
                t.rotate = props['angle']
            if 'image' in props:
                t.set_child(props['image'])
            t.update()
                            
    class Key():
        """
        Contains positioning and transformation data for every frame
        of a Spriter animation.
        """
        
        def __init__(self, time, properties):
            #The frame that this key applies to
            self.time = time
            
            #A dict of properties to iterate through
            self.properties = properties
            
    class Animation():
        """All the animation data."""
        def __init__(self, length, mainline, timelines):
            #All the keys of the animation, in a list
            self._mainline = mainline
            
            self._timelines = timelines
            
            #Length in frames
            self._length = length
            
        def update(self, time):
            """Renders child Bones or Parts"""
            while time > self._length:
                time -= length
            for timeline in timelines:
                key = _timeline.set_key(time)
            
    class Entity(SpriterObject):
        """
        The root-level SpriterObject. 
        Determines the total size of the thing, as well as the framerate.
        """
        def __init__(self, animations, width=300, height=800, refresh=30, speed=100, *args, **kwargs):
            super().__init__(*args, **kwargs)
            
            #A dict of all animations
            self.animations = animations
            for name in 'idle', 'Idle', 'default', 'Default', 'normal', 'Normal':
                if animations.contains(name):
                    self.current_anim = animations[name]
                    break
            
            #Dimensions in which the Entity operates (???)
            self.width = width
            self.height = height
            
            #The refresh rate
            self.refresh = float(refresh)
            
            #Animation speed in frames per second, this is different from the refresh rate
            self.speed = float(speed)
            
        def animate(self, name):
            """Starts an animation."""
            #set the animation's start time
            self.start = renpy.get_game_runtime()
            self.current_anim = self.animations[name]
            
        def render(self, width, height, st, at):
            #get the elapsed render time and calculate the current frame
            time = int((renpy.get_game_runtime() - self.start) / self.speed)
            
            current_anim.update(time)
            renpy.redraw(self, 1.0 / refresh)
            render = renpy.Render(self.width, self.height)
            for child in self._children:
                render.place(child)
            return render