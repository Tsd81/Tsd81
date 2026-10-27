export const register = on => {
  on('session.start', ($, e, next) => {
    $.ui.toast(`${$.plugin.name} е зареден ✓`)
    return next(e)
  })
}
