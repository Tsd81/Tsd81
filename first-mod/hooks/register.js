export const register = on => {
  on('session.start', ($, e, next) => {
    $.ui.toast(`${$.plugin.name} is loaded`)
    return next(e)
  })
}
