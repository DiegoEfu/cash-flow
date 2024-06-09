class StrAsNameMixin():
    """
    Simple mixin to return the name of the object when casted to str type. 
    """
    def __str__(self) -> str:
        return self.name